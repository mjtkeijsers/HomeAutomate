#!/usr/bin/env python3
"""Shared configuration and service helpers for HomeAut tasks."""

import json
import logging
import os
import re
import sys
import time
from functools import wraps

import requests
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient

import HomaAutInfluxWrite

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('homeautomation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("myPyllant").setLevel(logging.WARNING)

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


INFLUX_URL = get_env("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = get_env("INFLUX_TOKEN")
INFLUX_ORG = get_env("INFLUX_ORG", "ASML")
INFLUX_BUCKET = get_env("INFLUX_BUCKET", "youless")
TEST_MODE = False

REQUEST_TIMEOUT_DEFAULT = 10
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 0.5

_influx_client = None
_influx_client_created_at = None
_influx_client_max_age = 3600
_http_session = None


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
        if not INFLUX_TOKEN:
            raise RuntimeError("INFLUX_TOKEN is required for InfluxDB queries")
        if _influx_client is not None:
            try:
                _influx_client.close()
            except Exception as e:
                logger.warning(f"Error closing stale InfluxDB client: {e}")

        _influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        _influx_client_created_at = time.time()
        logger.debug("Created new InfluxDB client connection")

    return _influx_client

def write_to_influx(
    measurement_name, key1, value1, key2=None, value2=None, key3=None, value3=None
):
    """Write measurements to InfluxDB, or print them when running in test mode."""
    fields = {key1: value1}
    if key2 is not None and value2 is not None:
        fields[key2] = value2
    if key3 is not None and value3 is not None:
        fields[key3] = value3

    if TEST_MODE:
        print(
            f"[TEST MODE] InfluxDB write suppressed: "
            f"measurement={measurement_name!r}, fields={fields!r}",
            flush=True
        )
        return

    HomaAutInfluxWrite.write_to_influx(
        measurement_name,
        key1,
        value1,
        key2,
        value2,
        key3,
        value3,
        client=get_influx_client()
    )

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


def set_test_mode(enabled):
    global TEST_MODE
    TEST_MODE = enabled
