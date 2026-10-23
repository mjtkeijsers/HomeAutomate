#!/usr/bin/env python3
"""YoulessGas scheduled task."""

import requests

from HomeAutCommon import REQUEST_TIMEOUT_DEFAULT, logger, parse_youless_response, safe_request, safe_task, write_to_influx

@safe_task
def youless_gas_task():
    """Read gas meter data from Youless and write to InfluxDB."""
    logger.info("Running Youless Gas task...")

    try:
        response = safe_request("GET", "http://youless/e", timeout=REQUEST_TIMEOUT_DEFAULT)
    except requests.exceptions.RequestException:
        return

    data = parse_youless_response(response.text)
    gas = data.get('gas')

    if gas is not None:
        try:
            write_to_influx("gasmeter", "gas", gas)
            logger.info(f"Youless Gas: gas={gas}m3")
        except Exception as e:
            logger.error(f"Failed to write Youless Gas data to InfluxDB: {e}")
    else:
        logger.warning("Youless Gas: Missing gas value")
