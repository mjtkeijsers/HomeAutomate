#!/usr/bin/env python3
"""InfluxGas scheduled task."""

from HomeAutCommon import INFLUX_BUCKET, INFLUX_ORG, get_influx_client, logger, safe_task, write_to_influx

@safe_task
def influx_gas_task():
    """Calculate gas consumption rate from InfluxDB data."""
    logger.info("Running Influx Gas task...")
    measurement_name = "gas_actuals"

    try:
        client = get_influx_client()
        query_api = client.query_api()

        flux_query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -15m)
            |> filter(fn: (r) => r._measurement == "gasmeter")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: 2)
        '''

        result = query_api.query(flux_query, org=INFLUX_ORG)

        gas_values = []
        gas_times = []
        for table in result:
            for record in table.records:
                gas_values.append(record.get_value())
                gas_times.append(record.get_time())

        if len(gas_values) >= 2:
            gas_n0_f = gas_values[0]
            gas_n1_f = gas_values[1]
            time_n0 = gas_times[0]
            time_n1 = gas_times[1]

            time_diff = time_n0 - time_n1
            minutes_elapsed = time_diff.total_seconds() / 60

            if 3 <= minutes_elapsed <= 7:
                gas_m3_hr = (gas_n0_f - gas_n1_f) * (60 / minutes_elapsed)

                try:
                    write_to_influx(measurement_name, "gas_m3_hr", gas_m3_hr)
                    logger.info(f"Influx Gas: gas_m3_hr={gas_m3_hr:.4f} m3/h (interval: {minutes_elapsed:.1f} min)")
                except Exception as e:
                    logger.error(f"Failed to write Influx Gas data: {e}")
            else:
                logger.warning(f"Influx Gas: Unexpected interval {minutes_elapsed:.1f} minutes, skipping calculation")
        else:
            logger.warning(f"Influx Gas: Insufficient data from query (got {len(gas_values)} values)")

    except Exception as err:
        logger.error(f"Influx Gas task error: {err}")
