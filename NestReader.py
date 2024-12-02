import os
import requests
import time
import NestStore

def load_google_config(filename):
    # Get the home directory of the user
    home_directory = os.path.expanduser('~')
    # Construct the full path to the file
    file_path = os.path.join(home_directory, filename)

    key_value_pairs = []

    try:
        with open(file_path, 'r') as file:
            # Read the content of the file
            content = file.read()

            # Split the content by commas, strip whitespace, carriage returns, and line feeds
            pairs = [pair.strip().replace('\r', '').replace('\n', '') for pair in content.split(',')]

            print(pairs)

            for pair in pairs:

                key_value = pair.split('=')
                print(key_value)
                print(len(key_value))
                if len(key_value) == 2:
                    key, value = key_value
                    key_value_pairs.append((key.strip(), value.strip()))
                    print('c')

    except FileNotFoundError:
        print(f"File {filename} not found in the home directory.")

    return key_value_pairs


import csv
import os

# Define the path to the file in the user's home directory
file_path = os.path.expanduser('~/GoogleConfig.txt')

# Function to read and process the CSV file
def read_csv_to_dict(filename):

    
    # Get the home directory of the user
    home_directory = os.path.expanduser('~')
    # Construct the full path to the file
    file_path = os.path.join(home_directory, filename)


    config_dict = {}
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure the row is not empty
                key, value = row[0].strip(), row[1].strip()
                config_dict[key] = value
    return config_dict



# Example usage
if __name__ == '__main__':
    config = read_csv_to_dict('GoogleConfig.txt')
    print(config)

    project_id    = config['project_id']
    client_id     = config['client_id']
    client_secret = config['client_secret']
    redirect_uri  = config['redirect_uri']
    initial_token = config['refresh_token']

    print(project_id)
    print(client_id)
    print(client_secret)
    print(redirect_uri)
    print(initial_token)

    url = 'https://nestservices.google.com/partnerconnections/'+project_id+'/auth?redirect_uri='+redirect_uri+'&access_type=offline&prompt=consent&client_id='+client_id+'&response_type=code&scope=https://www.googleapis.com/auth/sdm.service'
    print("Go to this URL to log in:")
    print(url)
    #exit(0)


    params = (
        ('client_id', client_id),
        ('client_secret', client_secret),
        ('code', initial_token),
        ('grant_type', 'authorization_code'),
        ('redirect_uri', redirect_uri),
    )
    print('')
    print('')

    print('Params 1 = ' + str(params))

    response = requests.post('https://www.googleapis.com/oauth2/v4/token', params=params)

    response_json = response.json()

    print('JSON 1 = ' + str(response_json))

    print('')
    print('')

    access_token = response_json['token_type'] + ' ' + str(response_json['access_token'])
    print('Access token: ' + access_token)
    refresh_token = response_json['refresh_token']
    print('Refresh token: ' + refresh_token)

    # Get devices

    url_get_devices = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/' + project_id + '/devices'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': access_token,
        }

    response = requests.get(url_get_devices, headers=headers)

    print('')
    print('')

    print('JSON 3 = ' + str(response.json() ))

    print('')
    print('')

    response_json = response.json()
    device_0_name = response_json['devices'][0]['name']




    token_age  = 0
    temp_delay = 0

    while (1):
        token_age  = token_age  + 1
        temp_delay = temp_delay + 1

        #Once per 10 minutes suffices as the thermostat seems to refresh to cloud only once per 15 mins
        if (temp_delay == 2):
            temp_delay = 0;
            url_get_device = 'https://smartdevicemanagement.googleapis.com/v1/' + device_0_name

            headers = {
                'Content-Type': 'application/json',
                'Authorization': access_token,
                }

            try:
                response = requests.get(url_get_device, headers=headers)
                response.raise_for_status()

            
                #but this can fail like this: 
                #Thermo Data = {'error': {'code': 500, 'message': 'Internal error encountered.', 'status': 'INTERNAL'}}
    
                #if it works OK:
                #Thermo Data = {'name': 'enterprises/xxxetc', 'type': 'sdm.devices.types.THERMOSTAT', 'assignee': 'enterprises/xxETC', 
                # 'traits': {'sdm.devices.traits.Info': {'customName': ''}, 'sdm.devices.traits.Humidity': {'ambientHumidityPercent': 49}, 
                # 'sdm.devices.traits.Connectivity': {'status': 'ONLINE'}, 'sdm.devices.traits.Fan': {}, 'sdm.devices.traits.ThermostatMode':
                # {'mode': 'HEAT', 'availableModes': ['HEAT', 'OFF']}, 'sdm.devices.traits.ThermostatEco': {'availableModes': ['OFF', 'MANUAL_ECO'], 
                # 'mode': 'OFF', 'heatCelsius': 9.4444, 'coolCelsius': 24.44443}, 'sdm.devices.traits.ThermostatHvac': {'status': 'OFF'}, 
                #'sdm.devices.traits.Settings': {'temperatureScale': 'CELSIUS'}, 'sdm.devices.traits.ThermostatTemperatureSetpoint': 
                #{'heatCelsius': 15.94652}, 'sdm.devices.traits.Temperature': {'ambientTemperatureCelsius': 18.73}}, 
                #'parentRelations': [{'parent': 'enterprises/xxEtc', 'displayName': 'Eetkamer'}]}
        
                
                response_json = response.json()
    
                print('')
                print('Thermo Data = ' + str(response_json))
                print('')
                
                temperature = response_json['traits']['sdm.devices.traits.Temperature']['ambientTemperatureCelsius']
                print('Temperature:', temperature)
    
                setpoint = response_json['traits']['sdm.devices.traits.ThermostatTemperatureSetpoint']['heatCelsius']
                print('Setpoint:',setpoint)
    
                NestStore.store_to_influx(setpoint, temperature)

            except requests.exceptions.HTTPError as errh:
                print ("Http Error:",errh)
            except requests.exceptions.ConnectionError as errc:
                print ("Error Connecting:",errc)
            except requests.exceptions.Timeout as errt:
                print ("Timeout Error:",errt)
            except requests.exceptions.RequestException as err:
                print ("OOps: Something Else",err)

        
        if (token_age > 45):
            #Renew the access token which expires around 60 minutes.
            # By using > we have 15 attempts to refresh as age is only
            # reset when communication succeeds.
      
            print('renew access token')
            params = (
                ('client_id', client_id),
                ('client_secret', client_secret),
                ('refresh_token', refresh_token),
                ('grant_type', 'refresh_token'),
            )
            try:
                response = requests.post('https://www.googleapis.com/oauth2/v4/token', params=params)
                response.raise_for_status()

                response_json = response.json()
                access_token = response_json['token_type'] + ' ' + response_json['access_token']
                token_age = 0

                print('')
                print('')

            except requests.exceptions.HTTPError as errh:
                print ("Http Error:",errh)
            except requests.exceptions.ConnectionError as errc:
                print ("Error Connecting:",errc)
            except requests.exceptions.Timeout as errt:
                print ("Timeout Error:",errt)
            except requests.exceptions.RequestException as err:
                print ("OOps: Something Else",err)


        #One Minute, 60 seconds
        time.sleep(60)

