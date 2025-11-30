#!/usr/bin/env python
import requests
import InfluxWriter

res = requests.get("http://youless/e")

def filter_line(in_line):
    #"p1": 1234.345
    x = in_line.rfind(':') + 2 #For ';' and ' '
    y = len(line)
    return (float)((in_line[x:y]))
    

for line in res.text.split(','):
    #p1 = electra low
    if ("p1" in line.lower()): 
        p1 = filter_line(line)
 
    #p2 = electra high
    if ("p2" in line.lower()): 
        p2 = filter_line(line)
 
    #pwr = actual power
    if ("pwr" in line.lower()): 
        x = line.rfind(':') + 1 #For ';' , keep the sign as pwr can be negative
        y = len(line)
        pwr = (float)((line[x:y]))

InfluxWriter.write_to_influx("system", "electra_low", p1, "electra_high", p2, "pwr", pwr) 

