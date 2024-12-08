#!/usr/bin/env python

import datetime

from influxdb import InfluxDBClient

def store_to_influx(temperature):

    # influx configuration - edit these
    ifuser = "grafana"
    ifpass = "grafana"
    ifdb   = "youless"
    ifhost = "127.0.0.1"
    ifport = 8086
    measurement_name = "outside_temperature"

    # take a timestamp for this measurement
    time = datetime.datetime.utcnow()

    # connect to influx
    ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)

    temperature = float(temperature)

    # format the data as a single measurement for influx
    body = [
        {
            "measurement": measurement_name,
            "time": time,
            "fields": {
                "measured": temperature
            }
        }
    ]

    print (body)

    # write the measurement
    ifclient.write_points(body)

