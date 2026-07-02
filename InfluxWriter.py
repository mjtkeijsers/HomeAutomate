
import datetime
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

def write_to_influx(measurement_name, key1, value1, key2=None, value2=None, key3=None, value3=None):

    # influxdb 2.x configuration - edit these
    ifurl = "http://127.0.0.1:8086"
    iftoken = "your-api-token-here"  # Generate this in InfluxDB UI
    iforg = "your-org-here"
    ifbucket = "youless"

    # take a timestamp for this measurement
    time = datetime.datetime.utcnow()

    # connect to influx
    client = InfluxDBClient(url=ifurl, token=iftoken, org=iforg)
    write_api = client.write_api(write_options=SYNCHRONOUS)

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

    # write the measurement using InfluxDB 2.x API
    try:
        write_api.write(bucket=ifbucket, org=iforg, record=body)
    finally:
        client.close()

