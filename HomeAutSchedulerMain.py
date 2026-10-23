#!/usr/bin/env python3
"""Configure and run the HomeAutomate task scheduler."""

import argparse
import logging
import sys
import time

import schedule

from HomeAutCommon import INFLUX_TOKEN, close_http_session, close_influx_client, logger, set_test_mode
from HomeAutTaskInfluxGas import influx_gas_task
from HomeAutTaskInfluxLowestPower import influx_lowest_power_task
from HomeAutTaskOutsideWeather import outside_weather_task
from HomeAutTaskQingpingSensor import qingping_sensor_task
from HomeAutTaskShellyEM import shelly_em_task
from HomeAutTaskVaillantHeatPump import vaillant_heating_task
from HomeAutTaskYoulessElectra import youless_electra_task
from HomeAutTaskYoulessGas import youless_gas_task
from HomeAutTestAllTasks import run_test_tasks


def setup_schedule():
    """Configure all scheduled tasks."""
    schedule.every().minute.at(":00").do(youless_electra_task)
    schedule.every().minute.at(":00").do(shelly_em_task)

    for minute in [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]:
        schedule.every().hour.at(f":{minute:02d}").do(youless_gas_task).tag(f"youless_gas_{minute}")

    for minute in [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57]:
        schedule.every().hour.at(f":{minute:02d}").do(influx_gas_task).tag(f"influx_gas_{minute}")

    schedule.every(15).minutes.do(outside_weather_task)
    schedule.every().day.at("01:00").do(influx_lowest_power_task)
    schedule.every(10).minutes.do(qingping_sensor_task)
    schedule.every(10).minutes.do(vaillant_heating_task)

    logger.info("Schedule configured successfully")


def main():
    """Main application loop."""
    parser = argparse.ArgumentParser(description="Run the HomeAutomation scheduler.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="print InfluxDB measurements instead of writing them"
    )
    args = parser.parse_args()

    set_test_mode(args.test)
    if not args.test and not INFLUX_TOKEN:
        raise RuntimeError("INFLUX_TOKEN is required unless running with --test")

    if args.test:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting HomeAutomation application...")
    if args.test:
        logger.info("Test mode enabled: debug logging is active and InfluxDB writes will be printed to stdout")
    logger.info("================================")

    setup_schedule()

    try:
        if args.test:
            run_test_tasks()
            close_influx_client()
            close_http_session()
            return

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
