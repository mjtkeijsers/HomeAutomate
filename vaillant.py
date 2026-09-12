import asyncio
import os
from dotenv import load_dotenv
from myPyllant.api import MyPyllantAPI

# Load credentials from the .env file in the current directory
load_dotenv()

USERNAME = os.getenv("MYVAILLANT_USERNAME")
PASSWORD = os.getenv("MYVAILLANT_PASSWORD")
BRAND = os.getenv("MYVAILLANT_BRAND", "vaillant")
COUNTRY = os.getenv("MYVAILLANT_COUNTRY", "netherlands")


async def main():
    if not USERNAME or not PASSWORD:
        print("Error: MYVAILLANT_USERNAME or MYVAILLANT_PASSWORD not set in .env file.")
        return

    async with MyPyllantAPI(
        username=USERNAME,
        password=PASSWORD,
        brand=BRAND,
        country=COUNTRY,
    ) as api:

        async for system in api.get_systems():
            print("=" * 40)
            print(f"System ID: {system.id}")

            # Outdoor temperature check
            outdoor_temp = None
            if hasattr(system, "outdoor_temperature") and system.outdoor_temperature is not None:
                outdoor_temp = system.outdoor_temperature
            elif hasattr(system, "state") and isinstance(system.state, dict):
                outdoor_temp = system.state.get("outdoor_temperature")

            print(f"Outdoor Temperature: {outdoor_temp if outdoor_temp is not None else 'N/A'}C")
            print("-" * 40)

            # Heating zones
            if getattr(system, "zones", None):
                for zone in system.zones:
                    zone_name = getattr(zone, "name", "Unnamed Zone")
                    current_temp = getattr(zone, "current_room_temperature", None)
                    desired_temp = getattr(zone, "desired_room_temperature_setpoint", None)

                    print(f"Zone Name: {zone_name}")
                    print(f"  Current Temp: {current_temp if current_temp is not None else 'N/A'}C")
                    print(f"  Target Setpoint: {desired_temp if desired_temp is not None else 'N/A'}C")
                    print("-" * 20)
            else:
                print("No zones found.")


if __name__ == "__main__":
    asyncio.run(main())
