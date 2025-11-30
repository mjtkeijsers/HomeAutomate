#!/usr/bin/env python3
"""
Patched NestReader.py

- Fixes and improvements:
  * Use form-encoded POST (data=) for OAuth token exchanges instead of params=.
  * Always call response.raise_for_status() before consuming response.json().
  * Add timeouts to all requests to avoid hanging.
  * Defensive JSON parsing and key access with clear handling for missing fields.
  * Use expires_in from token responses to track token expiry and refresh properly.
  * Avoid printing secrets (mask sensitive values).
  * More granular exception handling (requests exceptions, JSON decode, KeyError/TypeError).
  * Log unexpected exceptions with stack traces instead of silently swallowing.
  * Graceful KeyboardInterrupt shutdown.
  * Use logging instead of prints for better diagnostics.
  * Wrap Influx writes to avoid breaking the main loop on write errors.
  * Clear comments explaining behavior.
"""

import time
import datetime
import logging
import sys
import json
import urllib.parse

import requests

import ConfigReader
import InfluxWriter

# Configuration for network calls and behavior
REQUEST_TIMEOUT = 10  # seconds for HTTP requests
MEASURE_INTERVAL = 120  # seconds between device measurements (original code measured every 2 minutes)
TOKEN_REFRESH_MARGIN = 300  # seconds before expiry to try refreshing (5 minutes)
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def mask_secret(s, keep=4):
    """Return a masked version of a secret for safe logging."""
    if not s:
        return "<empty>"
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep)


def obtain_tokens_with_code(client_id, client_secret, code, redirect_uri):
    """
    Exchange an authorization code for an access token and refresh token.
    Uses form-encoded POST as required by Google's OAuth token endpoint.
    Returns a dict with keys: access_token (str), token_type (str), refresh_token (optional), expires_in (int)
    Raises requests.RequestException or ValueError (JSON decode) on error.
    """
    token_url = "https://www.googleapis.com/oauth2/v4/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    logger.info("Requesting initial access token (authorization_code grant).")
    resp = requests.post(token_url, data=data, timeout=REQUEST_TIMEOUT)
        
    resp.raise_for_status()
    token_data = resp.json()

    # Validate minimal expected fields
    if "access_token" not in token_data or "token_type" not in token_data:
        raise ValueError("Token response missing access_token/token_type: %s" % token_data)

    return token_data


def refresh_access_token(client_id, client_secret, refresh_token):
    """
    Use the refresh_token grant to obtain a new access token.
    Returns token_data dict with access_token, token_type, expires_in, and optional refresh_token.
    Raises requests.RequestException or ValueError on error.
    """
    token_url = "https://www.googleapis.com/oauth2/v4/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    logger.info("Refreshing access token (refresh_token grant).")
    resp = requests.post(token_url, data=data, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    token_data = resp.json()

    if "access_token" not in token_data or "token_type" not in token_data:
        raise ValueError("Refresh token response missing access_token/token_type: %s" % token_data)

    return token_data


def get_devices(project_id, auth_header):
    """
    Get list of devices for the enterprise project.
    Returns a list of device dicts (may be empty).
    Raises requests.RequestException or ValueError on error.
    """
    url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{urllib.parse.quote_plus(project_id)}/devices"
    headers = {"Content-Type": "application/json", "Authorization": auth_header}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    devices = data.get("devices") or []
    return devices


def get_device(device_name, auth_header):
    """
    Retrieve a single device resource by resource name.
    device_name is expected to be the full resource name returned by the devices list.
    """
    url = f"https://smartdevicemanagement.googleapis.com/v1/{device_name}"
    headers = {"Content-Type": "application/json", "Authorization": auth_header}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_temperature_and_setpoint(device_json):
    """
    Parse temperature and setpoint from the device JSON.
    Returns (temperature, setpoint). If setpoint is unavailable because thermostat is OFF,
    setpoint is returned as 0.0.
    Raises KeyError/TypeError if structure is unexpected (caller should handle).
    """
    traits = device_json.get("traits", {})
    # Temperature trait
    temp_trait = traits.get("sdm.devices.traits.Temperature", {})
    temperature = temp_trait.get("ambientTemperatureCelsius")
    if temperature is None:
        raise KeyError("ambientTemperatureCelsius missing in device JSON")

    # Thermostat mode
    mode_trait = traits.get("sdm.devices.traits.ThermostatMode", {})
    mode = mode_trait.get("mode")

    setpoint = None
    if mode and mode != "OFF":
        setpoint_trait = traits.get("sdm.devices.traits.ThermostatTemperatureSetpoint", {})
        setpoint = setpoint_trait.get("heatCelsius")
        if setpoint is None:
            # If thermostat reports a mode other than OFF but has no setpoint,
            # treat as missing data (caller can decide to skip or use fallback).
            raise KeyError("Setpoint missing while thermostat mode is not OFF")
    else:
        setpoint = 0.0

    return float(temperature), float(setpoint)


def main():
    try:
        config = ConfigReader.read_csv_from_home_to_dict("GoogleConfig.txt")
    except Exception as e:
        logger.exception("Failed reading GoogleConfig.txt: %s", e)
        sys.exit(1)

    # Validate required config keys
    required_keys = ["project_id", "client_id", "client_secret", "redirect_uri", "refresh_token"]
    missing = [k for k in required_keys if k not in config or not config[k]]
    if missing:
        logger.error("Configuration missing required keys: %s", missing)
        sys.exit(1)

    project_id = config["project_id"]
    client_id = config["client_id"]
    client_secret = config["client_secret"]
    redirect_uri = config["redirect_uri"]
    initial_token_or_code = config.get("refresh_token")  # original script stored code in refresh_token at first run

    # Log non-secret parts; avoid logging actual secrets
    logger.info("Project ID: %s", project_id)
    logger.info("Client ID: %s", client_id)
    logger.info("Redirect URI: %s", redirect_uri)
    logger.info("Refresh token (masked): %s", mask_secret(initial_token_or_code))

    # Construct interactive authorization URL to help user if needed 
    auth_url = (
        "https://nestservices.google.com/partnerconnections/"
        + urllib.parse.quote_plus(project_id)
        + "/auth?redirect_uri="
        + urllib.parse.quote_plus(redirect_uri)
        + "&access_type=offline&prompt=consent&client_id="
        + urllib.parse.quote_plus(client_id)
        + "&response_type=code&scope=https://www.googleapis.com/auth/sdm.service"
    )
    logger.info("\n\nIf you need an authorization code, visit: %s \n\n", auth_url)

    '&response_type=code&scope=https://www.googleapis.com/auth/sdm.service'


    # Acquire tokens: the repository's original flow saved the "code" in GoogleConfig.txt as 'refresh_token' at first run.
    # Try to exchange that code for tokens. If initial_token_or_code is already a refresh token, the refresh flow below will work.
    access_token = None
    token_type = None
    refresh_token = None
    expires_at = 0  # epoch timestamp when access token expires

    # Determine whether the value is an authorization code (one-time) or already a refresh token.
    # We attempt an authorization_code exchange first; on failure we'll try assuming it's a refresh token.
    tried_code_exchange = False
    try:
        token_data = obtain_tokens_with_code(client_id, client_secret, initial_token_or_code, redirect_uri)
        tried_code_exchange = True
        access_token = token_data["access_token"]
        token_type = token_data["token_type"]
        refresh_token = token_data.get("refresh_token") or initial_token_or_code
        expires_in = int(token_data.get("expires_in") or 3600)
        expires_at = time.time() + expires_in
        logger.info("Successfully obtained access token (expires in %s seconds).", expires_in)
    except requests.HTTPError as e_http:
        # If the initial code exchange fails, it may be because the stored value was already a refresh token
        logger.warning("Initial code exchange failed (HTTP). Will attempt refresh_token flow if possible: %s", e_http)
    except requests.RequestException as e_req:
        logger.warning("Initial code exchange network error: %s", e_req)
    except ValueError as e_val:
        logger.warning("Initial code exchange returned unexpected payload: %s", e_val)
    except Exception:
        logger.exception("Unexpected error during initial token acquisition")

    # If we didn't obtain tokens via code exchange, try refresh_token flow using the stored value
    if not access_token:
        # Treat initial_token_or_code as a refresh token
        try:
            token_data = refresh_access_token(client_id, client_secret, initial_token_or_code)
            access_token = token_data["access_token"]
            token_type = token_data["token_type"]
            # some providers rotate refresh_token; prefer new one if present
            refresh_token = token_data.get("refresh_token") or initial_token_or_code
            expires_in = int(token_data.get("expires_in") or 3600)
            expires_at = time.time() + expires_in
            logger.info("Successfully obtained access token via refresh (expires in %s seconds).", expires_in)
        except requests.RequestException as e:
            logger.exception("Failed to obtain access token using refresh_token: %s", e)
            logger.error("Cannot continue without a valid access token. Please check GoogleConfig.txt and authorization flow.")
            sys.exit(1)
        except ValueError as e:
            logger.exception("Invalid token response while refreshing: %s", e)
            sys.exit(1)
        except Exception:
            logger.exception("Unexpected error while refreshing access token")
            sys.exit(1)

    # Build Authorization header
    auth_header = f"{token_type} {access_token}"

    # Retrieve devices and pick the first one (original script used devices[0]).
    try:
        devices = get_devices(project_id, auth_header)
    except requests.RequestException as e:
        logger.exception("Failed to get devices list: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error retrieving devices: %s", e)
        sys.exit(1)

    if not devices:
        logger.error("No devices found for project %s. Exiting.", project_id)
        sys.exit(1)

    device_0 = devices[0]
    device_0_name = device_0.get("name")
    if not device_0_name:
        logger.error("First device has no 'name' field. Device payload: %s", device_0)
        sys.exit(1)

    logger.info("Using device: %s", device_0_name)

    last_measure_time = 0

    try:
        while True:
            now = time.time()

            # Refresh token if it's within TOKEN_REFRESH_MARGIN of expiry
            if expires_at - now <= TOKEN_REFRESH_MARGIN:
                logger.info("Access token is nearing expiry; refreshing.")
                try:
                    token_data = refresh_access_token(client_id, client_secret, refresh_token)
                    access_token = token_data["access_token"]
                    token_type = token_data["token_type"]
                    refresh_token = token_data.get("refresh_token") or refresh_token
                    expires_in = int(token_data.get("expires_in") or 3600)
                    expires_at = time.time() + expires_in
                    auth_header = f"{token_type} {access_token}"
                    logger.info("Token refreshed; next expiry in %s seconds.", expires_in)
                except requests.RequestException as e:
                    logger.warning("Failed to refresh token (network/HTTP): %s", e)
                    # Don't exit: we'll try again later; but sleep a bit below to avoid tight loop
                except ValueError as e:
                    logger.warning("Invalid token response during refresh: %s", e)
                except Exception:
                    logger.exception("Unexpected error during token refresh")

            # Measurement interval: perform device query every MEASURE_INTERVAL seconds
            if now - last_measure_time >= MEASURE_INTERVAL:
                last_measure_time = now
                logger.info("Performing device measurement at %s", datetime.datetime.now().isoformat())

                try:
                    device_json = get_device(device_0_name, auth_header)
                except requests.HTTPError as e_http:
                    # Example: server returned error payload; log status
                    logger.warning("Device GET returned HTTP error: %s", e_http)
                    # If 401/403, the token might be invalid; force next loop to refresh sooner
                    if hasattr(e_http, "response") and e_http.response is not None and e_http.response.status_code in (401, 403):
                        # expire the token immediately to force refresh attempt
                        expires_at = 0
                    continue
                except requests.RequestException as e_req:
                    logger.warning("Device GET failed (network): %s", e_req)
                    continue
                except ValueError as e_json:
                    logger.warning("Device GET returned invalid JSON: %s", e_json)
                    continue
                except Exception:
                    logger.exception("Unexpected error fetching device")
                    continue

                # Defensive parsing of device JSON
                try:
                    temperature, setpoint = parse_temperature_and_setpoint(device_json)
                    logger.info("Temperature: %s C, Setpoint: %s C", temperature, setpoint)
                except (KeyError, TypeError) as e:
                    logger.warning("Missing or malformed data in device response: %s. Full payload: %s", e, device_json)
                    continue
                except Exception:
                    logger.exception("Unexpected error parsing device data")
                    continue

                # Write to Influx; ensure errors in writing don't break the main loop
                try:
                    # Original program used: InfluxWriter.write_to_influx("temperature", "setpoint", setpoint, "measured", temperature)
                    InfluxWriter.write_to_influx("temperature", "setpoint", setpoint, "measured", temperature)
                except Exception:
                    logger.exception("Failed to write to InfluxDB")

            # Sleep a short while to avoid busy looping; keep responsiveness for token refresh
            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Interrupted by user, exiting gracefully.")
    except Exception:
        logger.exception("Unexpected fatal error in main loop; exiting.")


if __name__ == "__main__":
    main()
