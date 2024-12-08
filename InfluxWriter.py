
import datetime

from influxdb import InfluxDBClient

def write_to_influx(measurement_name, key1, value1, key2=None, value2=None, key3=None, value3=None):

    # influx configuration - edit these
    ifuser = "grafana"
    ifpass = "grafana"
    ifdb   = "youless"
    ifhost = "127.0.0.1"
    ifport = 8086

    # take a timestamp for this measurement
    time = datetime.datetime.utcnow()

    # connect to influx
    ifclient = InfluxDBClient(ifhost,ifport,ifuser,ifpass,ifdb)


    # format the data as a single measurement for influx
    
    if (key2 == None):
        print('1 Value')

        value1 = float(value1)

        body = [
            {
                "measurement": measurement_name,
                "time": time,
                "fields": {
                    key1: value1
                }
            }
        ]
    
    elif (key3 == None):
        print('2 Value')

        value1 = float(value1)
        value2 = float(value2)

        body = [
            {
                "measurement": measurement_name,
                "time": time,
                "fields": {
                    key1: value1,
                    key2: value2
                }
            }
        ]
    else:
        print('3 Value')
        value1 = float(value1)
        value2 = float(value2)
        value3 = float(value3) 

        body = [
            {
                "measurement": measurement_name,
                "time": time,
                "fields": {
                    key1: value1,
                    key2: value2,
                    key3: value3
                }
            }
        ]
    
    print (body)

    # write the measurement
    ifclient.write_points(body)

