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
    
#read back last 2 most recent measurements.
query = 'select * from "gasmeter" ORDER BY DESC LIMIT 2'
r = ifclient.query(query)

s = "Result: {0}".format(r)

#
#Result: ResultSet({'('system', None)': [{'time': '2022-10-21T09:36:01.749038Z', 'electra_high': 6525.787, \
#'electra_low': 8302.422, 'gas': 5638.116, 'pwr': 216.0}, {'time': '2022-10-21T09:35:02.252935Z', 'electra_high'
#: 6525.783, 'electra_low': 8302.422, 'gas': 5638.116, 'pwr': 219.0}]})
# Removing the special characters to ensure no conversion errors in string to float.
#
for character in '[({})]':
    s = s.replace(character, '')

tokens = s.split(",")
print(tokens)
gas_n0_str = tokens[2]
gas_n1_str = tokens[4]


print(gas_n0_str)
print(gas_n1_str)
gas_n0_f = extract_value("gas",gas_n0_str)
gas_n1_f = extract_value("gas",gas_n1_str)
        
gas_last_minute = gas_n0_f - gas_n1_f

# take a timestamp for this measurement
time = datetime.datetime.utcnow()

# format the data as a single measurement for influx
body = [
    {
        "measurement": measurement_name,
        "time": time,
        "fields": {
            "gas_last_min": gas_last_minute
        }
    }
]

print (body)

# write the measurement
ifclient.write_points(body)

