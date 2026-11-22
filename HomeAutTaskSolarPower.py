#!/usr/bin/env python3
"""Detect solar power availability from the Youless meter."""

import logging

import requests

from HomeAutCommon import REQUEST_TIMEOUT_DEFAULT, parse_youless_response, safe_request, safe_task

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_solar_power_active = False
_consecutive_readings = 0
_REQUIRED_CONSECUTIVE_READINGS = 3


@safe_task
def solar_power_task():
    """Log solar power state changes after three consecutive readings."""
    global _solar_power_active, _consecutive_readings

    try:
        response = safe_request("GET", "http://youless/e", timeout=REQUEST_TIMEOUT_DEFAULT)
    except requests.exceptions.RequestException:
        _consecutive_readings = 0
        return

    data = parse_youless_response(response.text)
    power = data.get("pwr")
    if power is None:
        logger.warning("Youless solar power: Missing power value")
        _consecutive_readings = 0
        return

    try:
        power = float(power)
    except (TypeError, ValueError):
        logger.warning(f"Youless solar power: Invalid power value ({power!r})")
        _consecutive_readings = 0
        return

    if _solar_power_active:
        if power > 0:
            _consecutive_readings += 1
            if _consecutive_readings >= _REQUIRED_CONSECUTIVE_READINGS:
                logger.debug("solar power inactive, switch back setpoint")
                _solar_power_active = False
                _consecutive_readings = 0
        else:
            _consecutive_readings = 0
    elif power < 0:
        _consecutive_readings += 1
        if _consecutive_readings >= _REQUIRED_CONSECUTIVE_READINGS:
            logger.debug("solar power active, can switch on heat pump")
            _solar_power_active = True
            _consecutive_readings = 0
    else:
        _consecutive_readings = 0
