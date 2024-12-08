import InfluxWriter
import ConfigReader

import openmeteo_requests
import datetime
import requests_cache
from retry_requests import retry
import time

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"

config = ConfigReader.read_csv_from_home_to_dict("LocationConfig.txt")

latitude   = config['latitude']
longtitude = config['longtitude']

params = {
	"latitude": latitude,
	"longitude": longtitude,
	"current": "temperature_2m",
	"timezone": "auto",
	"past_days": 0
}

while(1):
	try:
		responses = openmeteo.weather_api(url, params=params)

		# Process first location. Add a for-loop for multiple locations or weather models
		response = responses[0]

		
		# Current values. The order of variables needs to be the same as requested.
		current = response.Current()
		
		print(current)

		current_temperature_2m = current.Variables(0).Value()
		
		InfluxWriter.write_to_influx("outside_temperature","measured", current_temperature_2m)
		

	except Exception as err:
		print ("OutsideWeather: Exception",err)
        
	#Sleep a few minutes
	time.sleep(5 * 60)
