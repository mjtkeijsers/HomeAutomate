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

    myflux.store_to_influx(99,88)


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
    exit(0)


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
        if (temp_delay == 10):
            temp_delay = 0;
            url_get_device = 'https://smartdevicemanagement.googleapis.com/v1/' + device_0_name

            headers = {
                'Content-Type': 'application/json',
                'Authorization': access_token,
                }

            response = requests.get(url_get_device, headers=headers)

            response_json = response.json()

            print('')
            print('Thermo Data = ' + str(response_json))
            print('')


            temperature = response_json['traits']['sdm.devices.traits.Temperature']['ambientTemperatureCelsius']
            print('Temperature:', temperature)

            setpoint = response_json['traits']['sdm.devices.traits.ThermostatTemperatureSetpoint']['heatCelsius']
            print('Setpoint:',setpoint)

            NestStore.store_to_influx(setpoint, temperature)

        if (token_age == 45):
            #Renew the access token which expires around 60 minutes.
            token_age = 0

            print('renew access token')
            params = (
                ('client_id', client_id),
                ('client_secret', client_secret),
                ('refresh_token', refresh_token),
                ('grant_type', 'refresh_token'),
            )

            response = requests.post('https://www.googleapis.com/oauth2/v4/token', params=params)

            response_json = response.json()
            access_token = response_json['token_type'] + ' ' + response_json['access_token']
            print('')
            print('')


        #One Minute, 60 seconds
        time.sleep(1)

