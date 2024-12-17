import requests
import time
import InfluxWriter
import datetime
import ConfigReader


# Example usage
if __name__ == '__main__':

    config = ConfigReader.read_csv_from_home_to_dict('GoogleConfig.txt')
    
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

    #If you did follow setup at google properly (and paid teh required 5 USD) then at initial run of
    # this script you will get the URL above AND an error below ;-).
    #
    # Use your browser, go to the URL and follow the steps untill you end up with google trying to
    #  reach your programmed redirect_uri (with server not found as most likely its a non existing
    #  page. 
    #
    # That is 'dont care' as inside that web URI you find a section starting with 4/, like
    #  4/0AanRRrtVApeftt7xIcFdVUekGgby236Hu1wXLkiR3ejaDstmBFvYNmSDGT9d_oLeCw
    #  You need to copy that value and put it in your GoogleConfig.txt file. After that is done
    #  properly restart the script and it will start its endless measuring loop!

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
    temp_delay = 1

    while (1):
        token_age  = token_age  + 1
        temp_delay = temp_delay + 1

        #Once per 10 minutes would suffice as the thermostat seems to refresh to cloud only once per 15 mins
        # for now we use 2 minutes to expedite learning and testing.
        if (temp_delay == 2):
            temp_delay = 0;
            url_get_device = 'https://smartdevicemanagement.googleapis.com/v1/' + device_0_name

            headers = {
                'Content-Type': 'application/json',
                'Authorization': access_token,
                }

            try:
                print("Go for next measurement at" + str(datetime.datetime.now()))
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
                response.raise_for_status()
                
                temperature = response_json['traits']['sdm.devices.traits.Temperature']['ambientTemperatureCelsius']
                print('Temperature:', temperature)
    
                setpoint = response_json['traits']['sdm.devices.traits.ThermostatTemperatureSetpoint']['heatCelsius']
                print('Setpoint:',setpoint)
        
                InfluxWriter.write_to_influx("temperature", "setpoint", setpoint, "measured", temperature)

            except requests.exceptions.HTTPError as errh:
                print ("NEST Http Error:",errh)
            except requests.exceptions.ConnectionError as errc:
                print ("NEST Error Connecting:",errc)
            except requests.exceptions.Timeout as errt:
                print ("NEST Timeout Error:",errt)
            except requests.exceptions.RequestException as err:
                print ("NEST OOps: Something Else",err)

        
        if (token_age > 6):
            #Renew the access token which expires around 60 minutes.
            # By using > we have multiple attempts to refresh as age is only
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

