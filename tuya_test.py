import os
import json
import sys
import tinytuya
import time

# Bepaal het pad naar keys.txt in dezelfde map als dit script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE = os.path.join(BASE_DIR, "keys.txt")

def laad_sleutels():
    """Leest de Tuya inloggegevens uit keys.txt."""
    if not os.path.exists(KEYS_FILE):
        print(f"❌ Fout: Het bestand '{KEYS_FILE}' is niet gevonden!")
        print("Maak dit bestand eerst aan met de juiste Device ID en Local Key.")
        sys.exit(1)

    try:
        with open(KEYS_FILE, "r") as f:
            data = json.load(f)

        # Controleer of alle benodigde velden aanwezig zijn
        benodigd = ["device_id", "local_key", "ip_address"]
        for veld in benodigd:
            if veld not in data or not data[veld]:
                print(f"❌ Fout: Het veld '{veld}' mist of is leeg in keys.txt!")
                sys.exit(1)

        return data
    except json.JSONDecodeError:
        print("❌ Fout: keys.txt bevat geen geldige JSON-structuur. Controleer de komma's en accolades!")
        sys.exit(1)

def test_stekker():
    # 1. Laad de configuratie uit het bestand
    config = laad_sleutels()
    print("✅ Sleutels succesvol ingeladen uit keys.txt.")

    # 2. Configureer de stekker met de ingeladen gegevens
    plug = tinytuya.OutletDevice(
        dev_id=config["device_id"],
        address=config["ip_address"],
        local_key=config["local_key"],
        version=3.3  # Jouw werkende versie
    )

    # 3. Maak verbinding en vraag status op
    print("Verbinding maken met de vijverpomp...")
    status = plug.status()

    if 'Error' in status or not status:
        print(f"❌ Kan geen verbinding maken lokaal. TinyTuya melding: {status}")
    else:
        print(f"✅ Succesvol verbonden! Huidige status: {status}")

        print("\nNu proberen te schakelen...")
        print("Schakelaar AAN zetten...")
        plug.turn_on()
        time.sleep(3)
        print("Schakelaar UIT zetten...")
        plug.turn_off()

if __name__ == "__main__":
    test_stekker()
