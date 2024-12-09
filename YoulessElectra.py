#!/usr/bin/env python

import datetime
import psutil
import requests
import InfluxWriter

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
    
measurement_name = "system"

InfluxWriter.write_to_influx(measurement_name, "electra_low", p1, "electra_high", p2, "pwr", pwr) 

