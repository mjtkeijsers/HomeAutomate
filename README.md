# HomeAutomate
Home Automation on Raspberry pi build around Youles, Influx, Grafana, Python, cron

This little project aims to build a dashboard on home gas and power use. When complete it shows 4 graphs:
-live power (refresh 1 minute)
-live gas (refresh 5 min)
-daily elektra ('today' as live)
-daily gas ('today' as live)

It requires a youless power monitor device to be connected to your gas and electra meter

<img width="1473" alt="image" src="https://user-images.githubusercontent.com/34219584/198372407-6ebea8fd-ed9b-4717-8266-c5d42ebc67f6.png">


The python files in this project are ran based on a crontab. See crontab.txt. 
-energy every minute
-sampling gas every 5 minutes
-calculation of delta in gas every 5 minutes, 1 minute behind sample.

The reason why energy needs just one step is in the different youless interface for electra and gas. Electra has a 'pwr' value which is actual consumption. Gas only has the meter reading hence to calculate actual you need to compare last 2 readings.

To get started:
-clone the project
-


