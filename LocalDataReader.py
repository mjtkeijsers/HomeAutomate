import base64
import os
import sys
import time
import requests

def load_keys(filename="qpkeys.txt"):
    """
    Lees APP_KEY en APP_SECRET uit een tekstbestand in dezelfde directory als het script.
    """
    # Bepaal het pad naar het sleutelbestand relatief ten opzichte van dit script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    key_file_path = os.path.join(script_dir, filename)

    if not os.path.exists(key_file_path):
        print(f"Fout: Het bestand '{filename}' is niet gevonden op pad: {key_file_path}")
        sys.exit(1)

    app_key = None
    app_secret = None

    with open(key_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Negeer lege regels of commentaarregels
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")  # Verwijder eventuele quotes

                if key == "APP_KEY":
                    app_key = value
                elif key == "APP_SECRET":
                    app_secret = value

    if not app_key or not app_secret:
        print(f"Fout: Zorg ervoor dat zowel APP_KEY als APP_SECRET zijn gedefinieerd in '{filename}'.")
        sys.exit(1)

    return app_key, app_secret

# Laad de keys in bij het starten
APP_KEY, APP_SECRET = load_keys()

# Endpoints
TOKEN_URL = "https://oauth.cleargrass.com/oauth2/token"
API_URL = "https://apis.cleargrass.com/v1/apis/devices"

def get_access_token():
    """Request a fresh OAuth 2.0 access token using App Key and App Secret"""
    credentials = f"{APP_KEY}:{APP_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    body = {
        "grant_type": "client_credentials",
        "scope": "device_full_access"
    }

    response = requests.post(TOKEN_URL, headers=headers, data=body)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Token Error [{response.status_code}]: {response.text}")
        return None

def fetch_sensor_data(access_token):
    """Fetch device data using the bearer token"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Qingping requires a timestamp parameter for freshness check
    params = {"timestamp": int(time.time() * 1000)}

    response = requests.get(API_URL, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        devices = data.get("devices", [])

        if not devices:
            print("No devices found linked to this account.")
            return

        for dev in devices:
            info = dev.get("info", {})
            device_name = info.get("name", "Unknown")
            mac = info.get("mac", "Unknown")
            sensor_data = dev.get("data", {})

            co2 = sensor_data.get("co2", {}).get("value", "N/A")
            temp = sensor_data.get("temperature", {}).get("value", "N/A")
            humidity = sensor_data.get("humidity", {}).get("value", "N/A")

            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] Device: {device_name} ({mac})")
            print(f"  -> CO2: {co2} ppm | Temp: {temp}°C | Humidity: {humidity}%")
            print("-" * 50)

    else:
        print(f"API Error [{response.status_code}]: {response.text}")

if __name__ == "__main__":
    print("Initializing Qingping Cloud API script...")

    while True:
        token = get_access_token()

        if token:
            fetch_sensor_data(token)
        else:
            print("Failed to obtain access token. Retrying in 60 seconds...")

        time.sleep(60)  
