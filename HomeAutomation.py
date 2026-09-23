#!/usr/bin/env python3
"""
HomeAutomation.py - Consolidated home automation application
Merges all cron-scheduled tasks into a single forever loop with proper timing.
Maintains database interactions with InfluxDB 2.x and Grafana compatibility.
"""

import requests
import re
import json
import InfluxWriter
import openmeteo_requests
import requests_cache
from retry_requests import retry
import datetime
from datetime import timedelta, timezone
import time
import sys
import logging
import schedule
import base64
import os
import asyncio
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from functools import wraps
from myPyllant.api import MyPyllantAPI

# Load environment variables from .env file if present
load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('homeautomation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# ENVIRONMENT HELPERS
# ============================================================================
def get_env(name, default=None, required=False, cast=None):
    """Read a required or optional environment variable with optional casting."""
    value = os.getenv(name, default)

    if value is None or str(value).strip() == "":
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return default

    if cast is not None:
        try:
            return cast(value)
        except (TypeError, ValueError):
            raise RuntimeError(f"Environment variable {name} is invalid for {cast.__name__}: {value!r}")

    return value


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================
INFLUX_URL = get_env("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = get_env("INFLUX_TOKEN", required=True)
INFLUX_ORG = get_env("INFLUX_ORG", "ASML")
INFLUX_BUCKET = get_env("INFLUX_BUCKET", "youless")

OUTSIDE_LATITUDE = get_env("OUTSIDE_LATITUDE", cast=float)
OUTSIDE_LONGITUDE = get_env("OUTSIDE_LONGITUDE", cast=float)

# Request timeouts and retry configuration
REQUEST_TIMEOUT_DEFAULT = 10  # seconds
REQUEST_TIMEOUT_SLOW_API = 15  # for slower APIs like Vaillant
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 0.5  # exponential backoff: 0.5s, 1s, 2s

# InfluxDB client connection pool (persistent, with staleness tracking)
_influx_client = None
_influx_client_created_at = None
_influx_client_max_age = 3600  # reconnect after 1 hour

# HTTP session for connection pooling (reusable across tasks)
_http_session = None

# ============================================================================
# QINGPING API CONFIGURATION (from environment variables only)
# ============================================================================
def load_qingping_keys():
    """Load Qingping credentials from environment variables."""
    app_key = get_env("QINGPING_APP_KEY")
    app_secret = get_env("QINGPING_APP_SECRET")

    if not app_key or not app_secret:
        logger.warning("Qingping credentials not configured. Qingping task will be skipped.")
        return None, None

    return app_key, app_secret


QP_APP_KEY, QP_APP_SECRET = load_qingping_keys()

QP_TOKEN_URL = "https://oauth.cleargrass.com/oauth2/token"
QP_API_URL = "https://apis.cleargrass.com/v1/apis/devices"

# ============================================================================
# VAILLANT API CONFIGURATION
# ============================================================================
VAILLANT_USERNAME = get_env("MYVAILLANT_USERNAME")
VAILLANT_PASSWORD = get_env("MYVAILLANT_PASSWORD")
VAILLANT_BRAND = get_env("MYVAILLANT_BRAND", "vaillant")
VAILLANT_COUNTRY = get_env("MYVAILLANT_COUNTRY", "netherlands")

# ============================================================================
# WEATHER API SETUP (Open-Meteo)
# ============================================================================
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_http_session():
    """Get or create a persistent HTTP session for connection pooling."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        logger.debug("Created new HTTP session for connection pooling")
    return _http_session


def close_http_session():
    """Close the persistent HTTP session."""
    global _http_session
    if _http_session is not None:
        _http_session.close()
        _http_session = None
        logger.debug("Closed HTTP session")


def get_influx_client(force_reconnect=False):
    """
    Get InfluxDB 2.x client connection with stale client detection.

    Automatically reconnects if the client has been open for more than
    _influx_client_max_age seconds to prevent connection timeouts.
    """
    global _influx_client, _influx_client_created_at

    # Check if client is stale
    if _influx_client is not None and not force_reconnect:
        age = time.time() - _influx_client_created_at
        if age > _influx_client_max_age:
            logger.info(f"InfluxDB client is stale ({age:.0f}s old), reconnecting...")
            force_reconnect = True

    # Create or reconnect
    if _influx_client is None or force_reconnect:
        if _influx_client is not None:
            try:
                _influx_client.close()
            except Exception as e:
                logger.warning(f"Error closing stale InfluxDB client: {e}")

        _influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        _influx_client_created_at = time.time()
        logger.debug("Created new InfluxDB client connection")

    return _influx_client


def close_influx_client():
    """Close the persistent InfluxDB client connection."""
    global _influx_client, _influx_client_created_at
    if _influx_client is not None:
        try:
            _influx_client.close()
        except Exception as e:
            logger.warning(f"Error closing InfluxDB client: {e}")
        _influx_client = None
        _influx_client_created_at = None


def safe_request(method, url, max_retries=RETRY_MAX_ATTEMPTS, timeout=REQUEST_TIMEOUT_DEFAULT, **kwargs):
    """
    Make an HTTP request with exponential backoff retry logic.

    Args:
        method: 'GET' or 'POST'
        url: Target URL
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
        **kwargs: Additional arguments passed to session.request()

    Returns:
        Response object on success, or None if all retries failed

    Raises:
        RequestException: If all retries are exhausted (caller should handle)
    """
    session = get_http_session()
    last_error = None

    for attempt in range(max_retries):
        try:
            logger.debug(f"HTTP {method} {url} (attempt {attempt + 1}/{max_retries})")
            response = session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(f"Request timeout on attempt {attempt + 1}/{max_retries}: {url}")
        except requests.exceptions.ConnectionError as e:
            last_error = e
            logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {url}")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code >= 500:
                last_error = e
                logger.warning(f"Server error {e.response.status_code} on attempt {attempt + 1}/{max_retries}: {url}")
            else:
                logger.error(f"Client error {e.response.status_code if e.response is not None else 'unknown'}: {url}")
                raise
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"Request error on attempt {attempt + 1}/{max_retries}: {e}")

        if attempt < max_retries - 1:
            wait_time = RETRY_BACKOFF_FACTOR * (2 ** attempt)
            logger.debug(f"Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)

    logger.error(f"All {max_retries} retry attempts failed for {url}: {last_error}")
    raise last_error


def parse_youless_response(response_text):
    """Parse Youless JSON response into a dictionary."""
    data = {}

    try:
        match = re.search(r'text=(\[.*\])', response_text, re.DOTALL)
        if match:
            json_str = match.group(1)
        elif response_text.strip().startswith('['):
            json_str = response_text.strip()
        else:
            logger.warning(f"Could not parse Youless response format: {response_text[:100]}")
            return data

        json_data = json.loads(json_str)

        if isinstance(json_data, list) and len(json_data) > 0:
            obj = json_data[0]
            if isinstance(obj, dict):
                data = obj

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in Youless response: {e}")
    except Exception as e:
        logger.error(f"Error parsing Youless response: {e}")

    return data


def safe_task(func):
    """Decorator to wrap scheduled tasks with error handling and duration logging."""
    @wraps(func)
    def wrapper():
        start_time = time.time()
        success = False
        try:
            func()
            success = True
        except requests.exceptions.RequestException as err:
            logger.error(f"{func.__name__} failed (network error): {err}")
        except (ValueError, KeyError, IndexError) as err:
            logger.error(f"{func.__name__} failed (data error): {err}")
        except Exception as err:
            logger.error(f"{func.__name__} failed (unexpected error): {err}", exc_info=True)
        finally:
            duration = time.time() - start_time
            status = "success" if success else "failed"
            logger.info(f"{func.__name__} {status} in {duration:.2f}s")

    return wrapper


# ============================================================================
# YOULESS ELECTRA TASK (every minute at :00)
# ============================================================================
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
            InfluxWriter.write_to_influx("system", "electra_low", p1, "electra_high", p2, "pwr", pwr)
            logger.info(f"Youless Electra: p1={p1} kWh, p2={p2} kWh, pwr={pwr} W")
        except Exception as e:
            logger.error(f"Failed to write Youless Electra data to InfluxDB: {e}")
    else:
        logger.warning(f"Youless Electra: Missing values (p1={p1}, p2={p2}, pwr={pwr})")


# ============================================================================
# YOULESS GAS TASK (every 5 minutes at :01, :06, :11, :16, :21, :26, :31, :36, :41, :46, :51, :56)
# ============================================================================
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
            InfluxWriter.write_to_influx("gasmeter", "gas", gas)
            logger.info(f"Youless Gas: gas={gas}m3")
        except Exception as e:
            logger.error(f"Failed to write Youless Gas data to InfluxDB: {e}")
    else:
        logger.warning("Youless Gas: Missing gas value")


# ============================================================================
# INFLUX GAS TASK (every 5 minutes at :02, :07, :12, :17, :22, :27, :32, :37, :42, :47, :52, :57)
# ============================================================================
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
                    InfluxWriter.write_to_influx(measurement_name, "gas_m3_hr", gas_m3_hr)
                    logger.info(f"Influx Gas: gas_m3_hr={gas_m3_hr:.4f} m3/h (interval: {minutes_elapsed:.1f} min)")
                except Exception as e:
                    logger.error(f"Failed to write Influx Gas data: {e}")
            else:
                logger.warning(f"Influx Gas: Unexpected interval {minutes_elapsed:.1f} minutes, skipping calculation")
        else:
            logger.warning(f"Influx Gas: Insufficient data from query (got {len(gas_values)} values)")

    except Exception as err:
        logger.error(f"Influx Gas task error: {err}")


# ============================================================================
# INFLUX LOWEST POWER TASK (daily at 01:00)
# ============================================================================
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
                    InfluxWriter.write_to_influx("sluip", "low", int(res))
                except Exception as e:
                    logger.error(f"Failed to write Lowest Power data to InfluxDB: {e}")
            else:
                logger.warning(f"Lowest Power for {s}: No data available")

            s = s + timedelta(days=1)

    except Exception as err:
        logger.error(f"Influx Lowest Power task error: {err}")


# ============================================================================
# OUTSIDE WEATHER TASK (every 15 minutes)
# ============================================================================
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
            InfluxWriter.write_to_influx("outside_temperature", "measured", current_temperature_2m)
            logger.info(f"Outside Weather: temperature={current_temperature_2m}°C")
        except Exception as e:
            logger.error(f"Failed to write Outside Weather data to InfluxDB: {e}")

    except Exception as err:
        logger.error(f"Outside Weather task error: {err}")


# ============================================================================
# QINGPING SENSOR TASK (every 10 minutes)
# ============================================================================
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
                        InfluxWriter.write_to_influx("qingping", "co2", co2, "temperature", temp, "humidity", humidity)
                        logger.info(f"Qingping Sensor [{device_name}]: co2={co2} ppm, temp={temp}°C, humidity={humidity}%")
                    except Exception as e:
                        logger.error(f"Failed to write Qingping data to InfluxDB: {e}")
                else:
                    logger.warning(f"Qingping Sensor [{device_name}]: Missing values (CO2={co2}, Temp={temp}, Humidity={humidity})")
        else:
            logger.error(f"Qingping API Error [{api_response.status_code}]: {api_response.text}")

    except Exception as err:
        logger.error(f"Qingping Sensor task error: {err}")


# ============================================================================
# VAILLANT HEATING SYSTEM TASK (every 10 minutes)
# ============================================================================
async def fetch_vaillant_data():
    """Fetch Vaillant heating system data from MyPyllant API."""
    if not VAILLANT_USERNAME or not VAILLANT_PASSWORD:
        logger.debug("Vaillant task skipped: MYVAILLANT_USERNAME or MYVAILLANT_PASSWORD not set in environment")
        return

    logger.info("Running Vaillant Heating System task...")

    try:
        async with MyPyllantAPI(
            username=VAILLANT_USERNAME,
            password=VAILLANT_PASSWORD,
            brand=VAILLANT_BRAND,
            country=VAILLANT_COUNTRY,
        ) as api:
            async for system in api.get_systems():
                logger.info(f"Processing Vaillant System ID: {system.id}")

                outdoor_temp = None
                if hasattr(system, "outdoor_temperature") and system.outdoor_temperature is not None:
                    outdoor_temp = system.outdoor_temperature
                elif hasattr(system, "state") and isinstance(system.state, dict):
                    outdoor_temp = system.state.get("outdoor_temperature")

                if outdoor_temp is not None:
                    try:
                        InfluxWriter.write_to_influx("vaillant_system", "outdoor_temperature", outdoor_temp)
                        logger.info(f"Vaillant: outdoor_temperature={outdoor_temp}°C")
                    except Exception as e:
                        logger.error(f"Failed to write Vaillant outdoor temp to InfluxDB: {e}")
                else:
                    logger.warning("Vaillant: outdoor_temperature not available")

                if getattr(system, "zones", None):
                    for zone in system.zones:
                        zone_name = getattr(zone, "name", "Unnamed Zone")
                        current_temp = getattr(zone, "current_room_temperature", None)
                        desired_temp = getattr(zone, "desired_room_temperature_setpoint", None)

                        zone_tag = zone_name.replace(" ", "_").replace("-", "_").lower()

                        if current_temp is not None:
                            try:
                                InfluxWriter.write_to_influx(
                                    f"vaillant_zone_{zone_tag}",
                                    "current_temperature",
                                    current_temp
                                )
                                logger.info(f"Vaillant Zone [{zone_name}]: current_temp={current_temp}°C")
                            except Exception as e:
                                logger.error(f"Failed to write Vaillant zone current temp to InfluxDB: {e}")
                        else:
                            logger.warning(f"Vaillant Zone [{zone_name}]: current_temperature not available")

                        if desired_temp is not None:
                            try:
                                InfluxWriter.write_to_influx(
                                    f"vaillant_zone_{zone_tag}",
                                    "desired_temperature",
                                    desired_temp
                                )
                                logger.info(f"Vaillant Zone [{zone_name}]: desired_temp={desired_temp}°C")
                            except Exception as e:
                                logger.error(f"Failed to write Vaillant zone desired temp to InfluxDB: {e}")
                        else:
                            logger.warning(f"Vaillant Zone [{zone_name}]: desired_temperature not available")
                else:
                    logger.warning("Vaillant: No zones found for this system")

    except Exception as err:
        logger.error(f"Vaillant Heating System task error: {err}")


@safe_task
def vaillant_heating_task():
    """Wrapper to run async Vaillant task in sync context."""
    try:
        asyncio.run(fetch_vaillant_data())
    except Exception as err:
        logger.error(f"Vaillant task wrapper failed: {err}")


# ============================================================================
# SCHEDULING SETUP
# ============================================================================
def setup_schedule():
    """Configure all scheduled tasks."""

    schedule.every().minute.at(":00").do(youless_electra_task)

    for minute in [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]:
        schedule.every().hour.at(f":{minute:02d}").do(youless_gas_task).tag(f"youless_gas_{minute}")

    for minute in [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57]:
        schedule.every().hour.at(f":{minute:02d}").do(influx_gas_task).tag(f"influx_gas_{minute}")

    schedule.every(15).minutes.do(outside_weather_task)
    schedule.every().day.at("01:00").do(influx_lowest_power_task)
    schedule.every(10).minutes.do(qingping_sensor_task)
    schedule.every(10).minutes.do(vaillant_heating_task)

    logger.info("Schedule configured successfully")


# ============================================================================
# MAIN LOOP
# ============================================================================
def main():
    """Main application loop."""
    logger.info("Starting HomeAutomation application...")
    logger.info("================================")

    setup_schedule()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("HomeAutomation stopped by user")
        close_influx_client()
        close_http_session()
        sys.exit(0)
    except Exception as err:
        logger.critical(f"Unexpected error in main loop: {err}", exc_info=True)
        close_influx_client()
        close_http_session()
        sys.exit(1)


if __name__ == "__main__":
    main()
