# Basic Power monitor

Home Automation on Raspberry pi build around **Youless** (see https://www.youless.nl/home.html), Influx, Grafana, Python, cron and **NEST** Thermostat.

This little project aims to build a dashboard on home gas and power use. When complete it shows these graphs:

-live power (refresh 1 minute)

-live gas (refresh 5 min)

-daily elektra ('today' as live)

-daily gas ('today' as live)

-OPTIONAL, Readout of setpoint and measured temperature NEST thermostat

-OPTIONAL, The temperature outside. Do note that the location where to obtain temperature in Outsideweather.py needs to be updated to your location. You can do this by putting a file name LocationConfig.txt in the users home directory with a value for longtitude and lattitude (as per demo file LocationConfig.txt)

-daily electra lowest value (what is 'leaking' all day, fridge, waterpump in pond etc)

It requires a **youless power monitor device** to be connected to your gas and electra meter. For the temoerature graphs you need a NEST thermostat and set up the OAuth2 protocol as specified in Dec 1 comment below. 

<img width="1505" alt="image" src="https://github.com/user-attachments/assets/56caf1c0-faa0-46ac-910c-3beb5dedb711">


The python files (excluding NEST read out at the moment) in this project are ran based on a crontab. See crontab.txt. 

-energy every minute

-sampling gas every 5 minutes

-calculation of delta in gas every 5 minutes, 1 minute behind sample.

The reason why energy needs just one step is in the different youless interface for electra and gas. Electra has a 'pwr' value which is actual consumption. Gas only has the meter reading hence to calculate actual you need to compare last 2 readings.

To get started:

-clone the project

-install grafana as per your target system, see https://pimylifeup.com/raspberry-pi-grafana/

-install influx as per your target system, see https://pimylifeup.com/raspberry-pi-influxdb/#using-influxdb-v1-on-your-raspberry-pi, for this project I used V1 of influx

-create the databases in influx

--command: influx

--command: database create youless

-install the python libraries to access influx:

--command:sudo pip3 install influxdb

-edit your crontab:

--> command:crontab -e

--> Copy the contact of crontab.txt and set the proper path.

--> Test: wait for a few minutes and run the check commands in influx.txt from terminal

-In case you also want to show the panel with NEST thermostat data:

-->python -u NestReader.py > logfile.txt&, which will write a sample every 2 minutes to influx.

-If that shows content; you have your data set up

-Next is to configure grafana 

--log in at grafana on localhost:3000

--Select influxdb as datasource first, URL is to set to http://localhost:8086, database name is youless

--load the dashboard as per the json file in the repo.

You should be good to go. 

--For the per day cost dashboard you need to update the queries to reflect your actual energy cost

--Can be you need to re-edit the panels to link the queries to influx properly (to be figured out what is missing in above if that is the case)

Code created and distribted under MIT license, go and have fun.

Change History:
08 December 2024, Added outside weather to dashboard, to do, lots of code cleanups as not very clean at the moment :-D

04 December 2024, with NestReader.py you have a neat very minmimal piece of code to monitor NEST.

01 December 2024: Added first pretty raw version of reading out my home NEST thermostat. Follewed manual and used code snippets from https://www.wouternieuwerth.nl/controlling-a-google-nest-thermostat-with-python/. Next step cleanup. 

28 Novermber 2024: After a crash of my raspberry recreated and step by step corrected manual. A tip if you use raspberry, use a high end SD card rather as the cheapest you can find. If you have a PI and a youless in your network the whole setup will take you about 2 hours.


