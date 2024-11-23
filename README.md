# HomeAutomate

Home Automation on Raspberry pi build around Youles, Influx, Grafana, Python, cron

This little project aims to build a dashboard on home gas and power use. When complete it shows 4 graphs:

-live power (refresh 1 minute)

-live gas (refresh 5 min)

-daily elektra ('today' as live)

-daily gas ('today' as live)

-daily electra lowest value (what is 'leaking' all day, fridge, waterpump in pond etc)

It requires a youless power monitor device to be connected to your gas and electra meter

<img width="1369" alt="image" src="https://user-images.githubusercontent.com/34219584/227767622-900c4bce-24ff-4f16-b749-0037e7d3f216.png">

The python files in this project are ran based on a crontab. See crontab.txt. 

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

-If that shows content; you have your data set up

-Next is to configure grafana 

--log in at grafana on localhost:3000

--Select influxdb as datasource first, URL is to set to http://localhost:8086, database name is youless

--load the dashboard as per the json file in the repo.

You should be good to go. 

--Can be you need to re-edit the panels to link the queries to influx properly (to be figured out what is missing in above if that is the case)

Code created and distribted under MIT license, go and have fun.


