#!/usr/bin/env python3
"""QingpingSensor scheduled task."""

import base64
import time

import requests

from HomeAutCommon import REQUEST_TIMEOUT_DEFAULT, get_env, logger, safe_request, safe_task, write_to_influx

def load_qingping_keys():
    app_key = get_env("QINGPING_APP_KEY")
    app_secret = get_env("QINGPING_APP_SECRET")

    if not app_key or not app_secret:
        logger.warning("Qingping credentials not configured. Qingping task will be skipped.")
        return None, None

    return app_key, app_secret


QP_APP_KEY, QP_APP_SECRET = load_qingping_keys()
QP_TOKEN_URL = "https://oauth.cleargrass.com/oauth2/token"
QP_API_URL = "https://apis.cleargrass.com/v1/apis/devices"

@safe_task
def qingping_sensor_task():
    """Fetch Qingping sensor data (CO2, humidity, temperature) and write to InfluxDB."""
    if QP_APP_KEY is None or QP_APP_SECRET is None:
        logger.debug("Qingping sensor task skipped: API keys not configured")
        return

    logger.info("Running Qingping Sensor task...")

    try:
        credentials = f"{QP_APP_KEY}:{QP_APP_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {
            "grant_type": "client_credentials",
            "scope": "device_full_access"
        }

        try:
            token_response = safe_request("POST", QP_TOKEN_URL, headers=headers, data=body, timeout=REQUEST_TIMEOUT_DEFAULT)
        except requests.exceptions.RequestException:
            return

        if token_response.status_code != 200:
            logger.error(f"Qingping Token Error [{token_response.status_code}]: {token_response.text}")
            return

        access_token = token_response.json().get("access_token")
        if not access_token:
            logger.error("Qingping: No access token received")
            return

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        params = {"timestamp": int(time.time() * 1000)}

        try:
            api_response = safe_request("GET", QP_API_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT_DEFAULT)
        except requests.exceptions.RequestException:
            return

        if api_response.status_code == 200:
            data = api_response.json()
            devices = data.get("devices", [])

            if not devices:
                logger.warning("Qingping: No devices found linked to this account")
                return

            for dev in devices:
                info = dev.get("info", {})
                device_name = info.get("name", "Unknown")
                sensor_data = dev.get("data", {})

                co2 = sensor_data.get("co2", {}).get("value")
                temp = sensor_data.get("temperature", {}).get("value")
                humidity = sensor_data.get("humidity", {}).get("value")

                if co2 is not None and temp is not None and humidity is not None:
                    try:
                        write_to_influx("qingping", "co2", co2, "temperature", temp, "humidity", humidity)
                        logger.info(f"Qingping Sensor [{device_name}]: co2={co2} ppm, temp={temp}°C, humidity={humidity}%")
                    except Exception as e:
                        logger.error(f"Failed to write Qingping data to InfluxDB: {e}")
                else:
                    logger.warning(f"Qingping Sensor [{device_name}]: Missing values (CO2={co2}, Temp={temp}, Humidity={humidity})")
        else:
            logger.error(f"Qingping API Error [{api_response.status_code}]: {api_response.text}")

    except Exception as err:
        logger.error(f"Qingping Sensor task error: {err}")
