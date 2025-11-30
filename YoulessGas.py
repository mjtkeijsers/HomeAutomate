#!/usr/bin/env python
import requests
import InfluxWriter

res = requests.get("http://youless/e")

#[{"tm":1733857410,"net": 9537.381,"pwr": 1030,"ts0":1729431000,
#  "cs0": 0.000,"ps0": 0,"p1": 14513.315,"p2": 9842.397,"n1": 4380.822,
#  "n2": 10437.509,"gas": 9361.314,"gts":2412102000}]

for line in res.text.split(','):
 
    #gas = gasmeter
    if ("gas" in line.lower()): 
        x = line.rfind(':') +  2 #For ';' and ' '
        y = len(line)
        gas = (float)((line[x:y]))    

measurement_name = "gasmeter"

InfluxWriter.write_to_influx(measurement_name, "gas", gas)
