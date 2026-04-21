#!/usr/bin/env python3
"""
HomeAutomation.py - Consolidated home automation application
Merges all cron-scheduled tasks into a single forever loop with proper timing.
Maintains database interactions with InfluxDB and Grafana compatibility.
"""

import requests
import InfluxWriter
import ConfigReader
import openmeteo_requests
import requests_cache
from retry_requests import retry
import datetime
from datetime import date, timedelta
import time
import sys
import logging
import schedule
from influxdb import InfluxDBClient

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/homeautomation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# INFLUX CONFIGURATION (shared across all functions)
# ============================================================================
INFLUX_USER = "grafana"
INFLUX_PASS = "grafana"
INFLUX_DB = "youless"
INFLUX_HOST = "127.0.0.1"
INFLUX_PORT = 8086

# ============================================================================
# WEATHER API SETUP (Open-Meteo)
# ============================================================================
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def extract_value(magic, in_string):
    """Extract a float value from a formatted string."""
    value_f = 0.0
    if magic in in_string.lower():
        x = in_string.rfind(':') + 2  # For ';' and ' '
        y = len(in_string)
        try:
            value_f = float(in_string[x:y])
        except ValueError:
            logger.warning(f"Could not convert value to float: {in_string[x:y]}")
    return value_f


def extract_value_with_end(magic, in_string, end_char='}'): 
    """Extract a float value from a formatted string with specific end character."""
    value_f = 0.0
    if magic in in_string.lower():
        x = in_string.rfind(':') + 2  # For ';' and ' '
        y = in_string.rfind(end_char) - 2  # For } and ]
        try:
            value_f = float(in_string[x:y])
        except ValueError:
            logger.warning(f"Could not convert value to float: {in_string[x:y]}")
    return value_f


def get_influx_client():
    """Get InfluxDB client connection."""
    return InfluxDBClient(INFLUX_HOST, INFLUX_PORT, INFLUX_USER, INFLUX_PASS, INFLUX_DB)


# ============================================================================
# YOULESS ELECTRA TASK (every minute at :00)
# ============================================================================
def youless_electra_task():
    """Read electricity data from Youless and write to InfluxDB."""
    try:
        logger.info("Running Youless Electra task...")
        res = requests.get("http://youless/e", timeout=10)
        
        p1 = None
        p2 = None
        pwr = None
        
        for line in res.text.split(','):
            # p1 = electra low
            if "p1" in line.lower():
                p1 = extract_value("p1", line)
            
            # p2 = electra high
            if "p2" in line.lower():
                p2 = extract_value("p2", line)
            
            # pwr = actual power
            if "pwr" in line.lower():
                x = line.rfind(':') + 1  # Keep the sign as pwr can be negative
                y = len(line)
                try:
                    pwr = float(line[x:y])
                except ValueError:
                    logger.warning(f"Could not parse power value: {line[x:y]}")
        
        if p1 is not None and p2 is not None and pwr is not None:
            InfluxWriter.write_to_influx("system", "electra_low", p1, "electra_high", p2, "pwr", pwr)
            logger.info(f"Youless Electra: p1={p1}, p2={p2}, pwr={pwr}")
        else:
            logger.warning("Youless Electra: Missing values")
    
    except Exception as err:
        logger.error(f"Youless Electra task failed: {err}")


# ============================================================================
# YOULESS GAS TASK (every 5 minutes at :01, :06, :11, :16, :21, :26, :31, :36, :41, :46, :51, :56)
# ============================================================================
def youless_gas_task():
    """Read gas meter data from Youless and write to InfluxDB."""
    try:
        logger.info("Running Youless Gas task...")
        res = requests.get("http://youless/e", timeout=10)
        
        gas = None
        for line in res.text.split(','):
            # gas = gasmeter
            if "gas" in line.lower():
                x = line.rfind(':') + 2  # For ';' and ' '
                y = len(line)
                try:
                    gas = float(line[x:y])
                except ValueError:
                    logger.warning(f"Could not parse gas value: {line[x:y]}")
        
        if gas is not None:
            measurement_name = "gasmeter"
            InfluxWriter.write_to_influx(measurement_name, "gas", gas)
            logger.info(f"Youless Gas: gas={gas}")
        else:
            logger.warning("Youless Gas: Missing gas value")
    
    except Exception as err:
        logger.error(f"Youless Gas task failed: {err}")


# ============================================================================
# INFLUX GAS TASK (every 5 minutes at :02, :07, :12, :17, :22, :27, :32, :37, :42, :47, :52, :57)
# ============================================================================
def influx_gas_task():
    """Calculate gas consumption rate from InfluxDB data."""
    try:
        logger.info("Running Influx Gas task...")
        measurement_name = "gas_actuals"
        
        # Connect to influx
        ifclient = get_influx_client()
        
        # Read back last 2 most recent measurements
        query = 'select * from "gasmeter" ORDER BY DESC LIMIT 2'
        r = ifclient.query(query)
        
        s = "Result: {0}".format(r)
        
        # Remove special characters to ensure no conversion errors
        for character in '[({})]':
            s = s.replace(character, '')
        
        tokens = s.split(",")
        
        if len(tokens) >= 5:
            gas_n0_str = tokens[2]
            gas_n1_str = tokens[4]
            
            gas_n0_f = extract_value("gas", gas_n0_str)
            gas_n1_f = extract_value("gas", gas_n1_str)
            
            gas_m3_hr = (gas_n0_f - gas_n1_f) * 12.0  # Convert 5 min sample to m3/h
            
            InfluxWriter.write_to_influx(measurement_name, "gas_m3_hr", gas_m3_hr)
            logger.info(f"Influx Gas: gas_m3_hr={gas_m3_hr}")
        else:
            logger.warning("Influx Gas: Insufficient data from query")
    
    except Exception as err:
        logger.error(f"Influx Gas task failed: {err}")


# ============================================================================
# INFLUX LOWEST POWER TASK (daily at 01:00)
# ============================================================================
def influx_lowest_power_task():
    """Calculate lowest power consumption for previous day."""
    try:
        logger.info("Running Influx Lowest Power task...")
        
        # Connect to influx
        ifclient = get_influx_client()
        
        # Start from yesterday
        s = date.today() - timedelta(days=1)
        
        while s < date.today():
            s2 = s + timedelta(days=1)
            
            # Query for evening minimum (8 PM - 11:59 PM)
            query_evening = (
                f"SELECT MIN(pwr) from system WHERE "
                f"time > '{s}T20:00:00.000000Z' AND "
                f"time < '{s}T23:59:00.000000Z' ORDER BY DESC"
            )
            r = ifclient.query(query_evening)
            res_evening = extract_value_with_end("min", f"Result: {r}")
            
            # Query for night minimum (12:01 AM - 5:00 AM next day)
            query_night = (
                f"SELECT MIN(pwr) from system WHERE "
                f"time > '{s2}T00:01:00.000000Z' AND "
                f"time < '{s2}T05:00:00.000000Z' ORDER BY DESC"
            )
            r = ifclient.query(query_night)
            res_night = extract_value_with_end("min", f"Result: {r}")
            
            res = min(res_evening, res_night)
            logger.info(f"Lowest Power for {s}: {res}W (evening: {res_evening}W, night: {res_night}W)")
            
            InfluxWriter.write_to_influx("sluip", "low", int(res))
            
            s = s + timedelta(days=1)
    
    except Exception as err:
        logger.error(f"Influx Lowest Power task failed: {err}")


# ============================================================================
# OUTSIDE WEATHER TASK (every 5 minutes)
# ============================================================================
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
# SCHEDULING SETUP
# ============================================================================
def setup_schedule():
    """Configure all scheduled tasks."""
    
    # Youless Electra: every minute at :00 seconds
    schedule.every().minute.at(":00").do(youless_electra_task)
    
    # Youless Gas: every 5 minutes at specific seconds
    # (minutes 1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56)
    for minute in [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]:
        schedule.every().hour.do(youless_gas_task).tag(f"youless_gas_{minute}")
    
    # Influx Gas: every 5 minutes at specific seconds
    # (minutes 2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57)
    for minute in [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57]:
        schedule.every().hour.do(influx_gas_task).tag(f"influx_gas_{minute}")
    
    # Outside Weather: every 5 minutes
    schedule.every(5).minutes.do(outside_weather_task)
    
    # Influx Lowest Power: daily at 01:00
    schedule.every().day.at("01:00").do(influx_lowest_power_task)
    
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
        sys.exit(0)
    except Exception as err:
        logger.critical(f"Unexpected error in main loop: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()