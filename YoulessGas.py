#!/usr/bin/env python

import datetime
import psutil
import requests
import InfluxWriter

res = requests.get("http://youless/e")

for line in res.text.split(','):
 
    #gas = gasmeter
    if ("gas" in line.lower()): 
        x = line.rfind(':') +  2 #For ';' and ' '
        y = len(line)
        gas = (float)((line[x:y]))    

measurement_name = "gasmeter"

InfluxWriter.write_to_influx(measurement_name, "gas", gas)
