#!/usr/bin/env python3
"""Compatibility entry point for the HomeAut scheduler."""

from HomeAutSchedulerMain import main
from HomeAutTaskInfluxGas import influx_gas_task
from HomeAutTaskInfluxLowestPower import influx_lowest_power_task
from HomeAutTaskOutsideWeather import outside_weather_task
from HomeAutTaskQingpingSensor import qingping_sensor_task
from HomeAutTaskShellyEM import shelly_em_task
from HomeAutTaskVaillantHeatPump import vaillant_heating_task
from HomeAutTaskYoulessElectra import youless_electra_task
from HomeAutTaskYoulessGas import youless_gas_task
from HomeAutTestAllTasks import run_test_tasks

if __name__ == "__main__":
    main()
