#!/usr/bin/env python3
"""YoulessElectra scheduled task."""

import requests

from HomeAutCommon import REQUEST_TIMEOUT_DEFAULT, logger, parse_youless_response, safe_request, safe_task, write_to_influx

@safe_task
def youless_electra_task():
    """Read electricity data from Youless and write to InfluxDB."""
    logger.info("Running Youless Electra task...")

    try:
        response = safe_request("GET", "http://youless/e", timeout=REQUEST_TIMEOUT_DEFAULT)
    except requests.exceptions.RequestException:
        return

    data = parse_youless_response(response.text)
    logger.debug(f"Youless Electra: raw_data={data}")

    p1 = data.get("p1")
    p2 = data.get('p2')
    pwr = data.get('pwr')

    if p1 is not None and p2 is not None and pwr is not None:
        try:
            write_to_influx("system", "electra_low", p1, "electra_high", p2, "pwr", pwr)
            logger.info(f"Youless Electra: p1={p1} kWh, p2={p2} kWh, pwr={pwr} W")
        except Exception as e:
            logger.error(f"Failed to write Youless Electra data to InfluxDB: {e}")
    else:
        logger.warning(f"Youless Electra: Missing values (p1={p1}, p2={p2}, pwr={pwr})")
