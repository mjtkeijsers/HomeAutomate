#!/usr/bin/env python3
"""Read power consumption from a Tuya local-network plug."""

import tinytuya

from HomeAutCommon import get_env, logger, safe_task, write_to_influx

TUYA_PP_DEVICE_ID = get_env("TUYA_PP_DEVICE_ID")
TUYA_PP_DEVICE_LOCALKEY = get_env("TUYA_PP_DEVICE_LOCALKEY")
TUYA_PP_DEVICE_IP = get_env("TUYA_PP_DEVICE_IP", "192.1.1.1")
TUYA_PP_PROTOCOL_VERSION = get_env("TUYA_PP_PROTOCOL_VERSION", "3.3", cast=float)
TUYA_PP_POWER_DP = get_env("TUYA_PP_POWER_DP", "19")


@safe_task
def tuya_power_plug_task():
    """Read plug power in watts and write it to InfluxDB in kilowatts."""
    if not TUYA_PP_DEVICE_ID or not TUYA_PP_DEVICE_LOCALKEY:
        logger.warning(
            "Tuya power plug task skipped: set TUYA_PP_DEVICE_ID and "
            "TUYA_PP_DEVICE_LOCALKEY in the environment"
        )
        return

    try:
        power_dp = int(TUYA_PP_POWER_DP)
    except ValueError:
        logger.error("Tuya power plug datapoint ID must be an integer: %r", TUYA_PP_POWER_DP)
        return

    logger.info("Running Tuya power plug task...")
    device = tinytuya.Device(
        TUYA_PP_DEVICE_ID,
        TUYA_PP_DEVICE_IP,
        TUYA_PP_DEVICE_LOCALKEY,
        version=TUYA_PP_PROTOCOL_VERSION,
    )
    update_response = device.updatedps([power_dp])
    logger.debug("Tuya power plug datapoint update response: %r", update_response)
    if isinstance(update_response, dict) and update_response.get("Error"):
        raise RuntimeError(
            f"Tuya power plug datapoint update failed: {update_response['Error']}"
        )

    status = device.status()

    if not isinstance(status, dict):
        logger.error("Tuya power plug returned an invalid status response")
        return

    if status.get("Error"):
        logger.error("Tuya power plug request failed: %s", status["Error"])
        return

    dps = status.get("dps")
    if not isinstance(dps, dict):
        logger.error("Tuya power plug response did not contain datapoints: %r", status)
        return

    logger.debug("Tuya power plug datapoints: %r", dps)
    power_watts = dps.get(TUYA_PP_POWER_DP)
    if power_watts is None:
        logger.warning(
            "Tuya power plug power datapoint %r was not present; available datapoints: %s",
            TUYA_PP_POWER_DP,
            ", ".join(dps),
        )
        return

    try:
        power_watts = float(power_watts)
    except (TypeError, ValueError):
        logger.error(
            "Tuya power plug datapoint %r is not numeric: %r",
            TUYA_PP_POWER_DP,
            power_watts,
        )
        return

    power_kw = power_watts / 1000.0
    write_to_influx("tuya_power_plug", "act_power_kw", power_kw)
    logger.info("Tuya power plug: act_power=%s W (%.3f kW)", power_watts, power_kw)
