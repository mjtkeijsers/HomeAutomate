#!/usr/bin/env python3
"""VaillantHeatPump scheduled task."""

import asyncio

from myPyllant.api import MyPyllantAPI

from HomeAutCommon import get_env, logger, safe_task, write_to_influx

VAILLANT_USERNAME = get_env("MYVAILLANT_USERNAME")
VAILLANT_PASSWORD = get_env("MYVAILLANT_PASSWORD")
VAILLANT_BRAND = get_env("MYVAILLANT_BRAND", "vaillant")
VAILLANT_COUNTRY = get_env("MYVAILLANT_COUNTRY", "netherlands")

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

                system_state = system.state.get("system", {}) if isinstance(system.state, dict) else {}
                system_flow_temperature = system_state.get("system_flow_temperature")
                system_water_pressure = system_state.get("system_water_pressure")

                system_fields = []
                system_values = []
                for field, value, unit in (
                    ("outdoor_temperature", outdoor_temp, "°C"),
                    ("system_flow_temperature", system_flow_temperature, "°C"),
                    ("system_water_pressure", system_water_pressure, "bar"),
                ):
                    if value is not None:
                        system_fields.extend((field, value))
                        system_values.append(f"{field}={value}{unit}")

                if system_fields:
                    try:
                        write_to_influx("vaillant_system", *system_fields)
                        logger.info(f"Vaillant System: {', '.join(system_values)}")
                    except Exception as e:
                        logger.error(f"Failed to write Vaillant system data to InfluxDB: {e}")
                else:
                    logger.warning("Vaillant: No system temperature or pressure values available")

                for circuit in system.circuits:
                    circuit_fields = []
                    circuit_values = []
                    if circuit.current_circuit_flow_temperature is not None:
                        circuit_fields.extend(
                            [
                                "current_circuit_flow_temperature",
                                circuit.current_circuit_flow_temperature,
                            ]
                        )
                        circuit_values.append(
                            f"current_flow_temperature="
                            f"{circuit.current_circuit_flow_temperature}°C"
                        )
                    if circuit.heating_circuit_flow_setpoint is not None:
                        circuit_fields.extend(
                            [
                                "heating_circuit_flow_setpoint",
                                circuit.heating_circuit_flow_setpoint,
                            ]
                        )
                        circuit_values.append(
                            f"heating_flow_setpoint="
                            f"{circuit.heating_circuit_flow_setpoint}°C"
                        )

                    if circuit_fields:
                        try:
                            write_to_influx(
                                f"vaillant_circuit_{circuit.index}",
                                *circuit_fields,
                            )
                            logger.info(
                                f"Vaillant Circuit [{circuit.index}]: "
                                f"{', '.join(circuit_values)}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to write Vaillant circuit "
                                f"{circuit.index} data to InfluxDB: {e}"
                            )
                    else:
                        logger.warning(
                            f"Vaillant Circuit [{circuit.index}]: "
                            "flow temperature and setpoint are unavailable"
                        )

                if getattr(system, "zones", None):
                    for zone in system.zones:
                        zone_name = getattr(zone, "name", "Unnamed Zone")
                        current_temp = getattr(zone, "current_room_temperature", None)
                        desired_temp = getattr(zone, "desired_room_temperature_setpoint", None)
                        current_humidity = getattr(zone, "current_room_humidity", None)

                        zone_tag = zone_name.replace(" ", "_").replace("-", "_").lower()

                        if current_temp is not None:
                            try:
                                write_to_influx(
                                    f"vaillant_zone_{zone_tag}",
                                    "current_temperature",
                                    current_temp)
                                logger.info(f"Vaillant Zone [{zone_name}]: current_temp={current_temp}°C")
                            except Exception as e:
                                logger.error(f"Failed to write Vaillant zone current temp to InfluxDB: {e}")
                        else:
                            logger.warning(f"Vaillant Zone [{zone_name}]: current_temperature not available")

                        if desired_temp is not None:
                            try:
                                write_to_influx(
                                    f"vaillant_zone_{zone_tag}",
                                    "desired_temperature",
                                    desired_temp)
                                logger.info(f"Vaillant Zone [{zone_name}]: desired_temp={desired_temp}°C")
                            except Exception as e:
                                logger.error(f"Failed to write Vaillant zone desired temp to InfluxDB: {e}")
                        else:
                            logger.warning(f"Vaillant Zone [{zone_name}]: desired_temperature not available")

                        if current_humidity is not None:
                            try:
                                write_to_influx(
                                    f"vaillant_zone_{zone_tag}",
                                    "current_room_humidity",
                                    current_humidity)
                                logger.info(
                                    f"Vaillant Zone [{zone_name}]: "
                                    f"current_room_humidity={current_humidity}%"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to write Vaillant zone humidity to InfluxDB: {e}"
                                )
                        else:
                            logger.warning(
                                f"Vaillant Zone [{zone_name}]: "
                                "current_room_humidity not available"
                            )
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
