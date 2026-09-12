#!/usr/bin/env python3
"""
HomeAutomation.py - Consolidated home automation application
Merges all cron-scheduled tasks into a single forever loop with proper timing.
Maintains database interactions with InfluxDB 2.x and Grafana compatibility.
"""

import requests
import re
import InfluxWriter
import ConfigReader
import openmeteo_requests
import requests_cache
from retry_requests import retry
import datetime
from datetime import date, timedelta, timezone
import time
import sys
import logging
import schedule
import base64
import os
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from functools import wraps

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
# INFLUX CONFIGURATION (shared across all functions)
# ============================================================================
INFLUX_URL = os.getenv("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "ASML")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "youless")

# Validate that critical config is present
if not INFLUX_TOKEN:
    logger.critical("INFLUX_TOKEN environment variable not set. Exiting.")
    sys.exit(1)

# InfluxDB client connection pool (persistent)
_influx_client = None

# ============================================================================
# QINGPING API CONFIGURATION (for Qingping sensor)
# ============================================================================
def load_qingping_keys(filename="qpkeys.txt"):
    """Load APP_KEY and APP_SECRET from qpkeys.txt file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    key_file_path = os.path.join(script_dir, filename)

    if not os.path.exists(key_file_path):
        logger.warning(f"Qingping keys file not found at {key_file_path}. Qingping task will be skipped.")
        return None, None

    app_key = None
    app_secret = None

    with open(key_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if key == "APP_KEY":
                    app_key = value
                elif key == "APP_SECRET":
                    app_secret = value

    if not app_key or not app_secret:
        logger.warning("Qingping keys not properly configured. Qingping task will be skipped.")
        return None, None

    return app_key, app_secret


QP_APP_KEY, QP_APP_SECRET = load_qingping_keys()

QP_TOKEN_URL = "https://oauth.cleargrass.com/oauth2/token"
QP_API_URL = "https://apis.cleargrass.com/v1/apis/devices"

# ============================================================================
# WEATHER API SETUP (Open-Meteo)
# ============================================================================
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_influx_client():
    """Get InfluxDB 2.x client connection (connection pooling)."""
    global _influx_client
    if _influx_client is None:
        _influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    return _influx_client


def close_influx_client():
    """Close the persistent InfluxDB client connection."""
    global _influx_client
    if _influx_client is not None:
        _influx_client.close()
        _influx_client = None


def parse_youless_response(response_text):
    """
    Parse Youless CSV response into a dictionary.
    
    Handles comma-separated key:value pairs with flexible formatting.
    Returns dict with lowercased keys and float values where parseable.
    """
    data = {}
    for line in response_text.split(','):
        line = line.strip()
        if ':' in line:
            key_part, value_part = line.split(':', 1)
            key = key_part.strip().lower()
            value_str = value_part.strip()
            
            try:
                # Handle potential sign for power values
                data[key] = float(value_str)
            except ValueError:
                logger.warning(f"Could not parse value for key '{key}': {value_str}")
    
    return data


def safe_task(func):
    """
    Decorator to wrap scheduled tasks with error handling and duration logging.
    
    Logs task duration and captures exceptions without breaking the scheduler.
    """
    @wraps(func)
    def wrapper():
        start_time = time.time()
        try:
            func()
        except Exception as err:
            logger.error(f"{func.__name__} failed: {err}", exc_info=True)
        finally:
            duration = time.time() - start_time
            logger.info(f"{func.__name__} completed in {duration:.2f}s")
    
    return wrapper


# ============================================================================
# YOULESS ELECTRA TASK (every minute at :00)
# ============================================================================
@safe_task
def youless_electra_task():
    """Read electricity data from Youless and write to InfluxDB."""
    try:
        logger.info("Running Youless Electra task...")
        res = requests.get("http://youless/e", timeout=10)
        
        data = parse_youless_response(res.text)
        
        p1 = data.get('p1')
        p2 = data.get('p2')
        pwr = data.get('pwr')
        
        if p1 is not None and p2 is not None and pwr is not None:
            InfluxWriter.write_to_influx("system", "electra_low", p1, "electra_high", p2, "pwr", pwr)
            logger.info(f"Youless Electra: p1={p1} kWh, p2={p2} kWh, pwr={pwr} W")
        else:
            logger.warning(f"Youless Electra: Missing values (p1={p1}, p2={p2}, pwr={pwr})")
    
    except Exception as err:
        logger.error(f"Youless Electra task failed: {err}")


# ============================================================================
# YOULESS GAS TASK (every 5 minutes at :01, :06, :11, :16, :21, :26, :31, :36, :41, :46, :51, :56)
# ============================================================================
@safe_task
def youless_gas_task():
    """Read gas meter data from Youless and write to InfluxDB."""
    try:
        logger.info("Running Youless Gas task...")
        res = requests.get("http://youless/e", timeout=10)
        
        data = parse_youless_response(res.text)
        gas = data.get('gas')
        
        if gas is not None:
            measurement_name = "gasmeter"
            InfluxWriter.write_to_influx(measurement_name, "gas", gas)
            logger.info(f"Youless Gas: gas={gas} m³")
        else:
            logger.warning("Youless Gas: Missing gas value")
    
    except Exception as err:
        logger.error(f"Youless Gas task failed: {err}")


# ============================================================================
# INFLUX GAS TASK (every 5 minutes at :02, :07, :12, :17, :22, :27, :32, :37, :42, :47, :52, :57)
# ============================================================================
@safe_task
def influx_gas_task():
    """Calculate gas consumption rate from InfluxDB data."""
    try:
        logger.info("Running Influx Gas task...")
        measurement_name = "gas_actuals"
        
        # Connect to influx
        client = get_influx_client()
        query_api = client.query_api()
        
        # Read back last 2 most recent measurements using Flux query language
        flux_query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -1h)
            |> filter(fn: (r) => r._measurement == "gasmeter")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: 2)
        '''
        
        try:
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
                
                # Calculate time difference in minutes
                time_diff = time_n0 - time_n1
                minutes_elapsed = time_diff.total_seconds() / 60
                
                # Validate interval (expect ~5 minutes, allow 3-7 minute window)
                if 3 <= minutes_elapsed <= 7:
                    # Convert measured 5-min sample to m3/h
                    gas_m3_hr = (gas_n0_f - gas_n1_f) * (60 / minutes_elapsed)
                    
                    InfluxWriter.write_to_influx(measurement_name, "gas_m3_hr", gas_m3_hr)
                    logger.info(f"Influx Gas: gas_m3_hr={gas_m3_hr:.4f} m³/h (interval: {minutes_elapsed:.1f} min)")
                else:
                    logger.warning(f"Influx Gas: Unexpected interval {minutes_elapsed:.1f} minutes, skipping calculation")
            else:
                logger.warning(f"Influx Gas: Insufficient data from query (got {len(gas_values)} values)")
        finally:
            # Don't close client here; keep connection pooled
            pass
    
    except Exception as err:
        logger.error(f"Influx Gas task failed: {err}")


# ============================================================================
# INFLUX LOWEST POWER TASK (daily at 01:00)
# ============================================================================
@safe_task
def influx_lowest_power_task():
    """Calculate lowest power consumption for previous day."""
    try:
        logger.info("Running Influx Lowest Power task...")
        
        # Connect to influx
        client = get_influx_client()
        query_api = client.query_api()
        
        # Use timezone-aware dates to avoid misalignment
        now_utc = datetime.datetime.now(timezone.utc)
        start_date = (now_utc - timedelta(days=1)).date()
        end_date = now_utc.date()
        
        try:
            s = start_date
            while s < end_date:
                s2 = s + timedelta(days=1)
                
                # Query for evening minimum (8 PM - 11:59 PM UTC)
                flux_query_evening = f'''
                    from(bucket: "{INFLUX_BUCKET}")
                    |> range(start: {s}T20:00:00Z, stop: {s}T23:59:00Z)
                    |> filter(fn: (r) => r._measurement == "system" and r._field == "pwr")
                    |> min()
                '''
                
                # Query for night minimum (12:01 AM - 5:00 AM UTC next day)
                flux_query_night = f'''
                    from(bucket: "{INFLUX_BUCKET}")
                    |> range(start: {s2}T00:01:00Z, stop: {s2}T05:00:00Z)
                    |> filter(fn: (r) => r._measurement == "system" and r._field == "pwr")
                    |> min()
                '''
                
                res_evening = None
                res_night = None
                
                # Get evening minimum
                try:
                    result_evening = query_api.query(flux_query_evening, org=INFLUX_ORG)
                    for table in result_evening:
                        for record in table.records:
                            res_evening = record.get_value()
                except Exception as e:
                    logger.warning(f"Could not retrieve evening minimum: {e}")
                
                # Get night minimum
                try:
                    result_night = query_api.query(flux_query_night, org=INFLUX_ORG)
                    for table in result_night:
                        for record in table.records:
                            res_night = record.get_value()
                except Exception as e:
                    logger.warning(f"Could not retrieve night minimum: {e}")
                
                # Determine the overall minimum
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
                    InfluxWriter.write_to_influx("sluip", "low", int(res))
                else:
                    logger.warning(f"Lowest Power for {s}: No data available")
                
                s = s + timedelta(days=1)
        finally:
            # Don't close client here; keep connection pooled
            pass
    
    except Exception as err:
        logger.error(f"Influx Lowest Power task failed: {err}")


# ============================================================================
# OUTSIDE WEATHER TASK (every 15 minutes)
# ============================================================================
@safe_task
def outside_weather_task():
    """Fetch outside weather from Open-Meteo API and write to InfluxDB."""
    try:
        logger.info("Running Outside Weather task...")
        
        config = ConfigReader.read_csv_from_home_to_dict("LocationConfig.txt")
        latitude = config['latitude']
        longitude = config['longtitude']  # Note: keeping original typo from config
        
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m",
            "timezone": "auto",
            "past_days": 0
        }
        
        url = "https://api.open-meteo.com/v1/forecast"
        responses = openmeteo.weather_api(url, params=params)
        
        # Process first location
        response = responses[0]
        
        # Get current values
        current = response.Current()
        current_temperature_2m = current.Variables(0).Value()
        
        InfluxWriter.write_to_influx("outside_temperature", "measured", current_temperature_2m)
        logger.info(f"Outside Weather: temperature={current_temperature_2m}°C")
    
    except Exception as err:
        logger.error(f"Outside Weather task failed: {err}")


# ============================================================================
# QINGPING SENSOR TASK (every 10 minutes)
# ============================================================================
@safe_task
def qingping_sensor_task():
    """Fetch Qingping sensor data (CO2, humidity, temperature) and write to InfluxDB."""
    if QP_APP_KEY is None or QP_APP_SECRET is None:
        logger.warning("Qingping sensor task skipped: API keys not configured")
        return

    try:
        logger.info("Running Qingping Sensor task...")

        # Get access token
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

        token_response = requests.post(QP_TOKEN_URL, headers=headers, data=body, timeout=10)
        if token_response.status_code != 200:
            logger.error(f"Qingping Token Error [{token_response.status_code}]: {token_response.text}")
            return

        access_token = token_response.json().get("access_token")
        if not access_token:
            logger.error("Qingping: No access token received")
            return

        # Fetch sensor data
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        params = {"timestamp": int(time.time() * 1000)}

        api_response = requests.get(QP_API_URL, headers=headers, params=params, timeout=10)

        if api_response.status_code == 200:
            data = api_response.json()
            devices = data.get("devices", [])

            if not devices:
                logger.warning("Qingping: No devices found linked to this account")
                return

            for dev in devices:
                info = dev.get("info", {})
                device_name = info.get("name", "Unknown")
                mac = info.get("mac", "Unknown")
                sensor_data = dev.get("data", {})

                co2 = sensor_data.get("co2", {}).get("value")
                temp = sensor_data.get("temperature", {}).get("value")
                humidity = sensor_data.get("humidity", {}).get("value")

                if co2 is not None and temp is not None and humidity is not None:
                    # Write all three values to InfluxDB in a single measurement
                    InfluxWriter.write_to_influx("qingping", "co2", co2, "temperature", temp, "humidity", humidity)
                    logger.info(f"Qingping Sensor [{device_name}]: co2={co2} ppm, temp={temp}°C, humidity={humidity}%")
                else:
                    logger.warning(f"Qingping Sensor [{device_name}]: Missing values (CO2={co2}, Temp={temp}, Humidity={humidity})")

        else:
            logger.error(f"Qingping API Error [{api_response.status_code}]: {api_response.text}")

    except Exception as err:
        logger.error(f"Qingping Sensor task failed: {err}")


# ============================================================================
# SCHEDULING SETUP
# ============================================================================
def setup_schedule():
    """Configure all scheduled tasks."""
    
    # Youless Electra: every minute at :00 seconds
    schedule.every().minute.at(":00").do(youless_electra_task)
    
    # Youless Gas: every 5 minutes at specific seconds
    # (minutes 1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56)
    for minute in [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]:
        schedule.every().hour.at(f":{minute:02d}").do(youless_gas_task).tag(f"youless_gas_{minute}")
    
    # Influx Gas: every 5 minutes at specific seconds
    # (minutes 2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57)
    for minute in [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57]:
        schedule.every().hour.at(f":{minute:02d}").do(influx_gas_task).tag(f"influx_gas_{minute}")
    
    # Outside Weather: every 15 minutes (not 5 as previously noted)
    schedule.every(15).minutes.do(outside_weather_task)
    
    # Influx Lowest Power: daily at 01:00 UTC
    schedule.every().day.at("01:00").do(influx_lowest_power_task)
    
    # Qingping Sensor: every 10 minutes (not 5 as previously noted)
    schedule.every(10).minutes.do(qingping_sensor_task)
    
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
        sys.exit(0)
    except Exception as err:
        logger.critical(f"Unexpected error in main loop: {err}", exc_info=True)
        close_influx_client()
        sys.exit(1)


if __name__ == "__main__":
    main()
