#!/usr/bin/env python3
"""
Refactored NestReader.py with improvements:
- Class-based structure for better state management
- Token persistence to config file
- Retry logic for transient failures
- Enhanced type hints and docstrings
- Signal handling for graceful shutdown
- More robust InfluxDB error handling
"""

import time
import datetime
import logging
import sys
import urllib.parse
from typing import Dict, Optional, Tuple, List, Any
import signal

import requests

# Assuming these are provided by other modules
import ConfigReader
import InfluxWriter

# Constants (consider moving to config)
REQUEST_TIMEOUT = 10  # seconds
MEASURE_INTERVAL = 120  # seconds
TOKEN_REFRESH_MARGIN = 300  # seconds
MAX_RETRIES = 3
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class NestClient:
    """Handles authentication and communication with Nest devices."""

    def __init__(self, config: Dict[str, str]):
        """Initialize with configuration dictionary."""
        self.config = config
        self.access_token: Optional[str] = None
        self.token_type: Optional[str] = None
        self.expires_at: float = 0
        self.auth_header: Optional[str] = None
        self.device_name: Optional[str] = None
        self.influx_failures: int = 0

        # Validate required config
        self._validate_config()

        # Set up signal handling
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _validate_config(self) -> None:
        """Validate the configuration dictionary."""
        required_keys = ["project_id", "client_id", "client_secret", "redirect_uri", "refresh_token"]
        missing = [k for k in required_keys if k not in self.config or not self.config[k]]
        if missing:
            logger.error("Configuration missing required keys: %s", missing)
            sys.exit(1)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle termination signals gracefully."""
        logger.info("Received signal %s, exiting", signum)
        sys.exit(0)

    @staticmethod
    def mask_secret(s: str, keep: int = 4) -> str:
        """Return a masked version of a secret for safe logging."""
        if not s:
            return "<empty>"
        if len(s) <= keep:
            return "*" * len(s)
        return s[:keep] + "*" * (len(s) - keep)

    def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> requests.Response:
        """Make an HTTP request with retries and timeout."""
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=REQUEST_TIMEOUT,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    "Request failed (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    wait_time,
                    str(e)
                )
                time.sleep(wait_time)
        return response  # Never reached, but makes linter happy

    def obtain_tokens_with_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        token_url = "https://www.googleapis.com/oauth2/v4/token"
        data = {
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.config["redirect_uri"],
        }

        logger.info("Requesting initial access token (authorization_code grant).")
        response = self._make_request("POST", token_url, data=data)
        token_data = response.json()

        if "access_token" not in token_data or "token_type" not in token_data:
            raise ValueError(f"Token response missing required fields: {token_data}")

        return token_data

    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the access token using the refresh token."""
        token_url = "https://www.googleapis.com/oauth2/v4/token"
        data = {
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "refresh_token": self.config["refresh_token"],
            "grant_type": "refresh_token",
        }

        logger.info("Refreshing access token (refresh_token grant).")
        response = self._make_request("POST", token_url, data=data)
        token_data = response.json()

        if "access_token" not in token_data or "token_type" not in token_data:
            raise ValueError(f"Refresh token response missing required fields: {token_data}")

        return token_data

    def update_config_with_new_token(self, token_data: Dict[str, Any]) -> None:
        """Update the config file with new token if it was refreshed."""
        if "refresh_token" in token_data:
            self.config["refresh_token"] = token_data["refresh_token"]
            try:
                ConfigReader.write_csv_to_home("GoogleConfig.txt", self.config)
                logger.info("Updated refresh token in config file")
            except Exception as e:
                logger.error("Failed to update config file: %s", e)

    def authenticate(self) -> None:
        """Authenticate with Nest API using either auth code or refresh token."""
        initial_token = self.config["refresh_token"]

        # Try authorization code flow first
        try:
            token_data = self.obtain_tokens_with_code(initial_token)
            self.access_token = token_data["access_token"]
            self.token_type = token_data["token_type"]
            self.expires_at = time.time() + int(token_data.get("expires_in", 3600))
            self.update_config_with_new_token(token_data)
            logger.info("Successfully obtained access token via auth code")
            return
        except Exception as e:
            logger.warning("Authorization code flow failed: %s. Trying refresh token flow...", e)

        # Fall back to refresh token flow
        try:
            token_data = self.refresh_access_token()
            self.access_token = token_data["access_token"]
            self.token_type = token_data["token_type"]
            self.expires_at = time.time() + int(token_data.get("expires_in", 3600))
            self.update_config_with_new_token(token_data)
            logger.info("Successfully obtained access token via refresh token")
        except Exception as e:
            logger.exception("Failed to authenticate with Nest API")
            sys.exit(1)

        self.auth_header = f"{self.token_type} {self.access_token}"

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get list of devices for the project."""
        url = (
            f"https://smartdevicemanagement.googleapis.com/v1/enterprises/"
            f"{urllib.parse.quote_plus(self.config['project_id'])}/devices"
        )
        headers = {"Content-Type": "application/json", "Authorization": self.auth_header}

        response = self._make_request("GET", url, headers=headers)
        return response.json().get("devices", [])

    def get_device(self, device_name: str) -> Dict[str, Any]:
        """Get details for a specific device."""
        url = f"https://smartdevicemanagement.googleapis.com/v1/{device_name}"
        headers = {"Content-Type": "application/json", "Authorization": self.auth_header}

        response = self._make_request("GET", url, headers=headers)
        return response.json()

    @staticmethod
    def parse_temperature_and_setpoint(device_json: Dict[str, Any]) -> Tuple[float, float]:
        """Parse temperature and setpoint from device JSON."""
        traits = device_json.get("traits", {})

        # Get temperature
        temp_trait = traits.get("sdm.devices.traits.Temperature", {})
        temperature = temp_trait.get("ambientTemperatureCelsius")
        if temperature is None:
            raise KeyError("ambientTemperatureCelsius missing in device JSON")

        # Get thermostat mode and setpoint
        mode_trait = traits.get("sdm.devices.traits.ThermostatMode", {})
        mode = mode_trait.get("mode")

        setpoint = 0.0
        if mode and mode != "OFF":
            setpoint_trait = traits.get("sdm.devices.traits.ThermostatTemperatureSetpoint", {})
            setpoint = setpoint_trait.get("heatCelsius")
            if setpoint is None:
                raise KeyError("Setpoint missing while thermostat mode is not OFF")

        return float(temperature), float(setpoint)

    def run(self) -> None:
        """Main execution loop: monitor device and write to InfluxDB."""
        try:
            # Authenticate and get devices
            self.authenticate()
            devices = self.get_devices()

            if not devices:
                logger.error("No devices found for project %
