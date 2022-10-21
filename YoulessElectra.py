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
measurement_name = "system"

# take a timestamp for this measurement
time = datetime.datetime.utcnow()

res = requests.get("http://youless/e")

for line in res.text.split(','):
    #p1 = electra low
    if ("p1" in line.lower()): 
        #"p1": 1234.345
        x = line.rfind(':') + 2 #For ';' and ' '
        y = len(line)
        p1 = (float)((line[x:y]))
 
    #p2 = electra high
    if ("p2" in line.lower()): 
        x = line.rfind(':') + 2 #For ';' and ' '
        y = len(line)
        p2 = (float)((line[x:y]))
 
    #pwr = actual power
    if ("pwr" in line.lower()): 
        x = line.rfind(':') + 1 #For ';' , keep the sign as pwr can be negative
        y = len(line)
        pwr = (float)((line[x:y]))
    

# connect to influx
ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)
    
#read back last most recent measurement.



# format the data as a single measurement for influx
body = [
    {
        "measurement": measurement_name,
        "time": time,
        "fields": {
            "electra_low": p1,
            "electra_high": p2,
            "pwr": pwr
        }
    }
]

print (body)

# write the measurement
ifclient.write_points(body)

