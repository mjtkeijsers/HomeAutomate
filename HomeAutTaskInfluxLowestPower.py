#!/usr/bin/env python3
"""InfluxLowestPower scheduled task."""

import datetime
from datetime import timedelta, timezone

from HomeAutCommon import INFLUX_BUCKET, INFLUX_ORG, get_influx_client, logger, safe_task, write_to_influx

@safe_task
def influx_lowest_power_task():
    """Calculate lowest power consumption for previous day."""
    logger.info("Running Influx Lowest Power task...")

    try:
        client = get_influx_client()
        query_api = client.query_api()

        now_utc = datetime.datetime.now(timezone.utc)
        start_date = (now_utc - timedelta(days=1)).date()
        end_date = now_utc.date()

        s = start_date
        while s < end_date:
            s2 = s + timedelta(days=1)

            flux_query_evening = f'''
                from(bucket: "{INFLUX_BUCKET}")
                |> range(start: {s}T20:00:00Z, stop: {s}T23:59:00Z)
                |> filter(fn: (r) => r._measurement == "system" and r._field == "pwr")
                |> min()
            '''

            flux_query_night = f'''
                from(bucket: "{INFLUX_BUCKET}")
                |> range(start: {s2}T00:01:00Z, stop: {s2}T05:00:00Z)
                |> filter(fn: (r) => r._measurement == "system" and r._field == "pwr")
                |> min()
            '''

            res_evening = None
            res_night = None

            try:
                result_evening = query_api.query(flux_query_evening, org=INFLUX_ORG)
                for table in result_evening:
                    for record in table.records:
                        res_evening = record.get_value()
            except Exception as e:
                logger.warning(f"Could not retrieve evening minimum: {e}")

            try:
                result_night = query_api.query(flux_query_night, org=INFLUX_ORG)
                for table in result_night:
                    for record in table.records:
                        res_night = record.get_value()
            except Exception as e:
                logger.warning(f"Could not retrieve night minimum: {e}")

            if res_evening is not None and res_night is not None:
                res = min(res_evening, res_night)
            elif res_evening is not None:
                res = res_evening
            elif res_night is not None:
                res = res_night
            else:
                res = None

            if res is not None:
                logger.info(f"Lowest Power for {s}: {res:.0f} W (evening: {res_evening} W, night: {res_night} W)")
                try:
                    write_to_influx("sluip", "low", int(res))
                except Exception as e:
                    logger.error(f"Failed to write Lowest Power data to InfluxDB: {e}")
            else:
                logger.warning(f"Lowest Power for {s}: No data available")

            s = s + timedelta(days=1)

    except Exception as err:
        logger.error(f"Influx Lowest Power task error: {err}")
