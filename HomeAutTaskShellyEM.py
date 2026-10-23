#!/usr/bin/env python3
"""ShellyEM scheduled task."""

import requests

from HomeAutCommon import REQUEST_TIMEOUT_DEFAULT, get_env, logger, safe_request, safe_task, write_to_influx

SHELLY_IP = get_env("SHELLY_IP", "192.168.1.217")

@safe_task
def shelly_em_task():
    """Read active power from Shelly EM Gen3, convert to kW, and write to InfluxDB."""
    logger.info("Running Shelly EM task...")

    url = f"http://{SHELLY_IP}/rpc/EM1.GetStatus?id=0"

    try:
        response = safe_request("GET", url, timeout=REQUEST_TIMEOUT_DEFAULT)
    except requests.exceptions.RequestException:
        return

    try:
        data = response.json()
    except Exception as err:
        logger.error(f"Shelly EM: JSON parsing error: {err}")
        return

    logger.debug(f"Shelly EM: raw_data={data}")
    act_power = data.get("act_power")

    if act_power is not None:
        try:
            power_watts = float(act_power)
            power_kw = power_watts / 1000.0

            write_to_influx("shelly", "act_power_kw", power_kw)
            logger.info(f"Shelly EM: act_power={power_watts} W ({power_kw:.3f} kW)")
        except Exception as err:
            logger.error(f"Failed to write Shelly EM data: {err}")
    else:
        logger.warning("Shelly EM: Missing 'act_power' value in response")
