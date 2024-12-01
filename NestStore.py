#!/usr/bin/env python

import datetime

from influxdb import InfluxDBClient

def store_to_influx(setpoint, temperature):

    # influx configuration - edit these
    ifuser = "grafana"
    ifpass = "grafana"
    ifdb   = "youless"
    ifhost = "127.0.0.1"
    ifport = 8086
    measurement_name = "temperature"

    # take a timestamp for this measurement
    time = datetime.datetime.utcnow()

    # connect to influx
    ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)


    # format the data as a single measurement for influx
    body = [
        {
            "measurement": measurement_name,
            "time": time,
            "fields": {
                "setpoint": setpoint,
                "measured": temperature
            }
        }
    ]

    print (body)

    # write the measurement
    ifclient.write_points(body)

