import datetime
import os
import logging
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)


def write_to_influx(
    measurement_name,
    key1,
    value1,
    key2=None,
    value2=None,
    key3=None,
    value3=None,
    client=None,
    write_api=None,
    bucket=None,
    org=None
):
    """
    Write data to InfluxDB 2.x
    
    Args:
        measurement_name: Name of the InfluxDB measurement
        key1: First field name
        value1: First field value
        key2: Second field name (optional)
        value2: Second field value (optional)
        key3: Third field name (optional)
        value3: Third field value (optional)
        client: Optional InfluxDBClient instance (for connection pooling)
        write_api: Optional write API instance
        bucket: Optional bucket name (overrides INFLUX_BUCKET env var)
        org: Optional organization name (overrides INFLUX_ORG env var)
    
    Reads InfluxDB configuration from environment variables if not provided:
    - INFLUX_URL (default: http://127.0.0.1:8086)
    - INFLUX_TOKEN (required)
    - INFLUX_ORG (default: your-org-here)
    - INFLUX_BUCKET (default: youless)
    
    If client and write_api are provided, they will be used directly.
    Otherwise, a new client will be created and closed after writing.
    """
    # Use provided client or create a new one
    own_client = False
    own_write_api = False
    
    if client is None:
        ifurl = os.getenv("INFLUX_URL", "http://127.0.0.1:8086")
        iftoken = os.getenv("INFLUX_TOKEN", "your-api-token-here")
        iforg = org or os.getenv("INFLUX_ORG", "your-org-here")
        ifbucket = bucket or os.getenv("INFLUX_BUCKET", "youless")
        
        client = InfluxDBClient(url=ifurl, token=iftoken, org=iforg)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        own_client = True
        own_write_api = True
    else:
        iforg = org or os.getenv("INFLUX_ORG", "your-org-here")
        ifbucket = bucket or os.getenv("INFLUX_BUCKET", "youless")
        if write_api is None:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            own_write_api = True
    
    try:
        # Take a timestamp for this measurement
        time = datetime.datetime.utcnow()
        
        # Build the data point
        fields = {key1: float(value1)}
        
        if key2 is not None and value2 is not None:
            fields[key2] = float(value2)
        
        if key3 is not None and value3 is not None:
            fields[key3] = float(value3)
        
        body = [
            {
                "measurement": measurement_name,
                "time": time,
                "fields": fields
            }
        ]
        
        logger.debug(f"Writing to InfluxDB: {body}")
        
        # Write the measurement using InfluxDB 2.x API
        write_api.write(bucket=ifbucket, org=iforg, record=body)
        
    except Exception as e:
        logger.error(f"Failed to write to InfluxDB: {e}")
        raise
    finally:
        # Only close resources we created ourselves
        if own_write_api:
            write_api.close()
        if own_client:
            client.close()
