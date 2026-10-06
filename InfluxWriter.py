
import datetime
import os
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def write_to_influx(measurement_name, key1, value1, key2=None, value2=None, key3=None, value3=None):
    """
    Write data to InfluxDB 2.x
    
    Reads InfluxDB credentials from environment variables:
    - INFLUX_URL (default: http://127.0.0.1:8086)
    - INFLUX_TOKEN (required)
    - INFLUX_ORG (default: your-org-here)
    - INFLUX_BUCKET (default: youless)
    """
    
    # Read InfluxDB configuration from environment variables
    ifurl = os.getenv("INFLUX_URL", "http://127.0.0.1:8086")
    iftoken = os.getenv("INFLUX_TOKEN", "your-api-token-here")
    iforg = os.getenv("INFLUX_ORG", "your-org-here")
    ifbucket = os.getenv("INFLUX_BUCKET", "youless")

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
<<<<<<< HEAD
        client.close()
=======
        client.close()
>>>>>>> 72a6840e9134f3b3190000a1a81d901cd8adddfc
