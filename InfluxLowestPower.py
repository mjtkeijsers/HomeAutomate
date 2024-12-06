#!/usr/bin/env python

import datetime
import psutil
import requests
import json
from datetime import date, timedelta
import time



from influxdb import InfluxDBClient

def extract_value(magic, in_string):  
    value_f = 0.0     
    
    if (magic in in_string.lower()): 
        x = in_string.rfind(':') +  2 #For ';' and ' '
        y = in_string.rfind('}') -  2 #For  } and ]
        value_f = (float)((in_string[x:y]))
        
    return value_f


# influx configuration
ifuser = "grafana"
ifpass = "grafana"
ifdb   = "youless"
ifhost = "127.0.0.1"
ifport = 8086

# connect to influx
ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)


#Start of the measurements
s = date.today() - timedelta(days = 1)

while (s < date.today()):

    s2 = s + timedelta(days = 1)
  
    query_evening = "SELECT MIN(pwr) from " + "system" + " WHERE time > '" + str(s) + "T20:00:00.000000Z' AND time < '"+ str(s) + "T23:59:00.000000Z' ORDER BY DESC"
    r = ifclient.query(query_evening)
    res_evening = extract_value("min", "Result: {0}".format(r))
 
    query_night = "SELECT MIN(pwr) from " + "system" + " WHERE time > '" + str(s2) + "T00:01:00.000000Z' AND time < '"+ str(s2) + "T05:00:00.000000Z' ORDER BY DESC"
    r = ifclient.query(query_night)
    res_night = extract_value("min", "Result: {0}".format(r))
 
    res = min(res_evening, res_night)
    print(str(s) + " = " + str(res))    
    

    # format the data as a single measurement for influx
    body = [
        {
            "measurement": "sluip",
            "time": datetime.datetime.utcnow(),
            "fields": {
                "low": int(res)
            }
        }
    ]


    print (body)

    i = ifclient.write_points(body)
    print(i)
    
    s = s + timedelta(days = 1)
  
    
    
