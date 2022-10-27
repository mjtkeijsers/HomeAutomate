#!/usr/bin/env python

import datetime
import psutil
import requests
import json

from influxdb import InfluxDBClient

def extract_value(magic, in_string):  
    value_f = 0.0     
    
    if (magic in in_string.lower()): 
        x = in_string.rfind(':') +  2 #For ';' and ' '
        y = len(in_string)
        value_f = (float)((in_string[x:y]))
        
    return value_f


# influx configuration
ifuser = "grafana"
ifpass = "grafana"
ifdb   = "youless"
ifhost = "127.0.0.1"
ifport = 8086
measurement_name = "gas_actuals"

# connect to influx
ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)

# take a timestamp for this measurement
time = datetime.datetime.utcnow() 

print(time)    
#read back last measurement of a date.
query = "SELECT * from " + "gasmeter" + " WHERE time < '2022-10-24' AND time > '2022-10-22' ORDER BY DESC LIMIT 1"

print(query)
r = ifclient.query(query)

s = "Result: {0}".format(r)

print(s)
