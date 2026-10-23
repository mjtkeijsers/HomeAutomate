#!/usr/bin/env python3
"""OutsideWeather scheduled task."""

import openmeteo_requests
import requests_cache
from retry_requests import retry

from HomeAutCommon import get_env, logger, safe_task, write_to_influx

OUTSIDE_LATITUDE = get_env("OUTSIDE_LATITUDE", cast=float)
OUTSIDE_LONGITUDE = get_env("OUTSIDE_LONGITUDE", cast=float)

cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

@safe_task
def outside_weather_task():
    """Fetch outside weather from Open-Meteo API and write to InfluxDB."""
    logger.info("Running Outside Weather task...")

    if OUTSIDE_LATITUDE is None or OUTSIDE_LONGITUDE is None:
        logger.warning("Outside Weather task skipped: OUTSIDE_LATITUDE / OUTSIDE_LONGITUDE not configured")
        return

    try:
        params = {
            "latitude": OUTSIDE_LATITUDE,
            "longitude": OUTSIDE_LONGITUDE,
            "current": "temperature_2m",
            "timezone": "auto",
            "past_days": 0
        }

        url = "https://api.open-meteo.com/v1/forecast"
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        current = response.Current()
        current_temperature_2m = current.Variables(0).Value()

        try:
            write_to_influx("outside_temperature", "measured", current_temperature_2m)
            logger.info(f"Outside Weather: temperature={current_temperature_2m}°C")
        except Exception as e:
            logger.error(f"Failed to write Outside Weather data to InfluxDB: {e}")

    except Exception as err:
        logger.error(f"Outside Weather task error: {err}")
