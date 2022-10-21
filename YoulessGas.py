#!/usr/bin/env python

import datetime
import psutil
import requests

from influxdb import InfluxDBClient

# influx configuration - edit these
ifuser = "grafana"
ifpass = "grafana"
ifdb   = "youless"
ifhost = "127.0.0.1"
ifport = 8086
measurement_name = "gasmeter"

# take a timestamp for this measurement
time = datetime.datetime.utcnow()

res = requests.get("http://youless/e")

for line in res.text.split(','):
 
    #gas = gasmeter
    if ("gas" in line.lower()): 
        x = line.rfind(':') +  2 #For ';' and ' '
        y = len(line)
        gas = (float)((line[x:y]))    

# connect to influx
ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)
   

# format the data as a single measurement for influx
body = [
    {
        "measurement": measurement_name,
        "time": time,
        "fields": {
            "gas": gas
        }
    }
]

print (body)

# write the measurement
ifclient.write_points(body)

