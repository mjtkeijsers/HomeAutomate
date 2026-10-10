# HomeAutomate - Home Power and Energy Monitoring

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive **home automation and energy monitoring system** built on Raspberry Pi using **Youless energy monitors**, **InfluxDB 2.x**, **Grafana**, and **Python**. This project provides real-time and historical visibility into your home's power and gas consumption, along with environmental data from various sensors.

---

## Features

### Core Monitoring
- **Live Power Consumption** - Real-time electricity usage (1-minute refresh)
- **Live Gas Consumption** - Real-time gas usage tracking (5-minute refresh)
- **Daily Energy Tracking** - Daily electricity and gas usage with live "today" views
- **Baseload Analysis** - Identifies always-on power consumption (fridge, pumps, etc.)
- **Gas Flow Rate Calculation** - Derived m³/hour from meter readings

### Sensor Integration
- **Youless Electra/Gas Meters** - Primary energy monitoring
- **Qingping Sensors** - CO₂, temperature, and humidity monitoring
- **Vaillant Heating System** - Outdoor temperature, zone temperatures, and setpoints
- **Open-Meteo Weather** - External temperature data for context

### Visualization
- **Grafana Dashboard** - Pre-configured dashboard JSON included
- **InfluxDB 2.x** - Time-series data storage with Flux query support

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         HomeAutomate                               │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    HomeAutomation.py                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │  │
│  │  │  Scheduler   │  │   Tasks      │  │  InfluxDB    │          │  │
│  │  │  (schedule)  │──▶│  (async/sync)│──▶│  Client Pool │          │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│       ▲                  ▲                  ▲                        │
│       │                  │                  │                        │
│  ┌────┴────┐      ┌─────┴─────┐      ┌─────┴─────┐                 │
│  │Youless  │      │Qingping  │      │Vaillant  │                 │
│  │  API    │      │  API     │      │  API     │                 │
│  └─────────┘      └──────────┘      └──────────┘                 │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    InfluxDB 2.x                                  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Buckets: youless (default)                               │  │
│  │  Measurements: system, gasmeter, gas_actuals, sluip,         │  │
│  │                 outside_temperature, qingping, vaillant_*      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Grafana                                       │
│  Pre-configured dashboard with energy and sensor visualizations    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

### 1. Consolidated Scheduling
Instead of multiple cron jobs, **HomeAutomation.py** uses a single Python process with the `schedule` library. This provides:
- **Centralized control** - One process to monitor and manage
- **Connection pooling** - Reusable HTTP and InfluxDB clients
- **Consistent error handling** - Unified logging and retry logic
- **Precise timing** - Tasks run at exact minute marks (e.g., :00, :05, :10)

### 2. Connection Management
- **InfluxDB Client Pooling**: A single client is maintained and reused across all tasks, with automatic reconnection after 1 hour of inactivity
- **HTTP Session Pooling**: A persistent `requests.Session` reduces connection overhead for API calls
- **Stale Connection Detection**: Clients are automatically reconnected if they've been idle too long

### 3. Error Handling Strategy
- **Task-Level Decorators**: `@safe_task` decorator wraps every task with consistent error handling
- **Exponential Backoff**: HTTP requests automatically retry with increasing delays (0.5s, 1s, 2s)
- **Graceful Degradation**: Failed tasks log errors but don't crash the entire application
- **Comprehensive Logging**: All operations logged with timestamps, durations, and error details

### 4. Configuration Management
- **Environment Variables**: All sensitive data (tokens, credentials) loaded from `.env` file
- **Sensible Defaults**: Non-critical settings have fallback values
- **Type Safety**: Environment variables are cast to appropriate types (int, float, bool)

---

## Data Flow

### Task Scheduling
| Task | Frequency | Data Source | Measurements |
|------|-----------|--------------|--------------|
| Youless Electra | Every minute (:00) | Youless API | system (p1, p2, pwr) |
| Youless Gas | Every 5 min (:01, :06, ...) | Youless API | gasmeter (gas) |
| Influx Gas Rate | Every 5 min (:02, :07, ...) | InfluxDB | gas_actuals (gas_m3_hr) |
| Lowest Power | Daily at 01:00 | InfluxDB | sluip (low) |
| Outside Weather | Every 15 min | Open-Meteo API | outside_temperature (measured) |
| Qingping Sensors | Every 10 min | Qingping API | qingping (co2, temperature, humidity) |
| Vaillant Heating | Every 10 min | MyPyllant API | vaillant_system, vaillant_zone_* |

### InfluxDB Schema
```
Bucket: youless (configurable via INFLUX_BUCKET)

Measurements:
  system          - Electricity: electra_low (p1), electra_high (p2), pwr
  gasmeter        - Gas: gas (m³)
  gas_actuals     - Gas rate: gas_m3_hr (m³/h)
  sluip           - Baseload: low (W)
  outside_temperature - Weather: measured (°C)
  qingping        - Sensors: co2 (ppm), temperature (°C), humidity (%)
  vaillant_system  - Heating: outdoor_temperature (°C)
  vaillant_zone_*  - Zones: current_temperature (°C), desired_temperature (°C)
```

---

## Project Structure

```
HomeAutomate/
├── HomeAutomation.py    # Main application with scheduler and all tasks
├── InfluxWriter.py      # InfluxDB write helper with connection pooling support
├── GrafanaDashboard.json # Pre-configured Grafana dashboard
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variable template (create from .env)
└── README.md
```

---

## Quick Start

### Prerequisites
- Raspberry Pi (or any Linux system)
- Python 3.8+
- **Youless energy monitor** (LS120 or similar) connected to your meters
- InfluxDB 2.x server (local or remote)
- Grafana server (local or remote)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mjtkeijsers/HomeAutomate.git
   cd HomeAutomate
   ```

2. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   # Create .env file from the reference in README
   # Or copy from a template if available
   nano .env
   ```

4. **Set up InfluxDB:**
   - Create a bucket (default: `youless`)
   - Create an API token with write access
   - Configure in `.env`:
     ```
     INFLUX_URL=http://localhost:8086
     INFLUX_TOKEN=your-api-token
     INFLUX_ORG=your-org
     INFLUX_BUCKET=youless
     ```

5. **Configure data sources:**
   - Youless: Ensure device is on network (default: `http://youless/e`)
   - Qingping: Set `QINGPING_APP_KEY` and `QINGPING_APP_SECRET`
   - Vaillant: Set `MYVAILLANT_USERNAME`, `MYVAILLANT_PASSWORD`
   - Weather: Set `OUTSIDE_LATITUDE` and `OUTSIDE_LONGITUDE`

4. **Run the application:**
   ```bash
   python3 HomeAutomation.py
   ```

5. **Set up Grafana:**
   - Add InfluxDB 2.x data source
   - Import `GrafanaDashboard.json`

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INFLUX_URL` | No | `http://127.0.0.1:8086` | InfluxDB server URL |
| `INFLUX_TOKEN` | Yes | - | InfluxDB API token |
| `INFLUX_ORG` | No | `ASML` | InfluxDB organization |
| `INFLUX_BUCKET` | No | `youless` | InfluxDB bucket |
| `OUTSIDE_LATITUDE` | No | - | Latitude for weather data |
| `OUTSIDE_LONGITUDE` | No | - | Longitude for weather data |
| `QINGPING_APP_KEY` | No | - | Qingping API key |
| `QINGPING_APP_SECRET` | No | - | Qingping API secret |
| `MYVAILLANT_USERNAME` | No | - | Vaillant/MyPyllant username |
| `MYVAILLANT_PASSWORD` | No | - | Vaillant/MyPyllant password |
| `MYVAILLANT_BRAND` | No | `vaillant` | Heating system brand |
| `MYVAILLANT_COUNTRY` | No | `netherlands` | Country for API |

### requirements.txt
```
influxdb-client>=1.18.0
requests>=2.28.0
requests-cache>=1.0.0
retry-requests>=2.0.0
openmeteo-requests>=1.0.0
schedule>=1.1.0
python-dotenv>=1.0.0
myPyllant>=1.0.0
```

---

## Code Architecture

### HomeAutomation.py

The main application follows a **single-process, scheduled-task** architecture:

```python
# Connection Management (global, pooled)
_influx_client = None      # Persistent InfluxDB client
_http_session = None       # Persistent HTTP session

# Task Decorator
@safe_task
def example_task():
    """All tasks use this decorator for consistent error handling."""
    client = get_influx_client()  # Gets pooled client
    # ... do work ...
    InfluxWriter.write_to_influx(..., client=client)  # Reuses client

# Scheduler Setup
def setup_schedule():
    schedule.every().minute.at(":00").do(youless_electra_task)
    schedule.every().hour.at(":01").do(youless_gas_task)
    # ... etc

# Main Loop
def main():
    setup_schedule()
    while True:
        schedule.run_pending()
        time.sleep(1)
```

### Key Components

#### 1. **Connection Pooling (`get_influx_client()`)**
```python
def get_influx_client(force_reconnect=False):
    global _influx_client, _influx_client_created_at
    
    # Auto-reconnect if client is stale (>1 hour old)
    if _influx_client is not None and not force_reconnect:
        age = time.time() - _influx_client_created_at
        if age > _influx_client_max_age:
            force_reconnect = True
    
    if _influx_client is None or force_reconnect:
        # Create new client
        _influx_client = InfluxDBClient(url=INFLUX_URL, 
                                         token=INFLUX_TOKEN, 
                                         org=INFLUX_ORG)
        _influx_client_created_at = time.time()
    
    return _influx_client
```

#### 2. **Safe Task Decorator**
```python
def safe_task(func):
    @wraps(func)
    def wrapper():
        start_time = time.time()
        success = False
        try:
            func()
            success = True
        except Exception as err:
            logger.error(f"{func.__name__} failed: {err}", exc_info=True)
        finally:
            duration = time.time() - start_time
            status = "success" if success else "failed"
            logger.info(f"{func.__name__} {status} in {duration:.2f}s")
    return wrapper
```

#### 3. **HTTP Request with Retry**
```python
def safe_request(method, url, max_retries=3, timeout=10, **kwargs):
    """Exponential backoff retry: 0.5s, 1s, 2s"""
    session = get_http_session()
    for attempt in range(max_retries):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except (Timeout, ConnectionError) as e:
            last_error = e
            wait_time = 0.5 * (2 ** attempt)
            time.sleep(wait_time)
    raise last_error
```

#### 4. **InfluxWriter with Client Pooling**
```python
def write_to_influx(measurement_name, key1, value1, ..., client=None, ...):
    """
    If client is provided, reuse it (connection pooling).
    Otherwise, create a new client and close it after writing.
    """
    own_client = False
    
    if client is None:
        client = InfluxDBClient(url=ifurl, token=iftoken, org=iforg)
        own_client = True
    
    try:
        # Build and write data point
        write_api.write(bucket=ifbucket, org=iforg, record=body)
    finally:
        if own_client:
            client.close()
```

---

## Task Details

### Youless Electra Task
- **Frequency**: Every minute at :00
- **API**: `http://youless/e`
- **Data**: p1 (low tariff kWh), p2 (high tariff kWh), pwr (instantaneous power W)
- **Output**: `system` measurement with electra_low, electra_high, pwr fields

### Youless Gas Task
- **Frequency**: Every 5 minutes (offset by 1 minute)
- **API**: `http://youless/e` (same endpoint, different field)
- **Data**: gas (meter reading m³)
- **Output**: `gasmeter` measurement with gas field

### Influx Gas Rate Task
- **Frequency**: Every 5 minutes (offset by 2 minutes)
- **Data Source**: InfluxDB query of last 2 gas readings
- **Calculation**: `(latest - previous) * (60 / minutes_elapsed)` = m³/hour
- **Output**: `gas_actuals` measurement with gas_m3_hr field

### Lowest Power Task
- **Frequency**: Daily at 01:00
- **Data Source**: InfluxDB query
- **Calculation**: Minimum power consumption during evening (20:00-23:59) and night (00:01-05:00)
- **Output**: `sluip` measurement with low field (baseload in watts)

### Outside Weather Task
- **Frequency**: Every 15 minutes
- **API**: Open-Meteo (https://api.open-meteo.com/v1/forecast)
- **Data**: Current temperature at configured latitude/longitude
- **Output**: `outside_temperature` measurement with measured field

### Qingping Sensor Task
- **Frequency**: Every 10 minutes
- **API**: ClearGrass OAuth2 + Devices API
- **Authentication**: Client credentials flow
- **Data**: CO₂ (ppm), temperature (°C), humidity (%) for each device
- **Output**: `qingping` measurement with co2, temperature, humidity fields

### Vaillant Heating Task
- **Frequency**: Every 10 minutes
- **API**: MyPyllant API (async)
- **Data**: Outdoor temperature, zone temperatures, desired setpoints
- **Output**: `vaillant_system` (outdoor_temperature), `vaillant_zone_*` (current_temperature, desired_temperature)

---

## Best Practices

### For Production Use
1. **Use systemd service** for automatic startup and restart on crash
2. **Rotate logs** - Configure log rotation for `homeautomation.log`
3. **Monitor the monitor** - Set up alerts if data stops flowing
4. **Backup InfluxDB** - Regular backups of your time-series data
5. **Use HTTPS** - If exposing APIs, use HTTPS and proper authentication

### For Development
1. **Mock APIs** - Use mock responses for testing without hardware
2. **Test individual tasks** - Run tasks manually for debugging (see below)
3. **Check InfluxDB queries** - Verify Flux queries in InfluxDB UI
4. **Validate data** - Spot-check measurements against physical meters

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| No data in InfluxDB | Missing INFLUX_TOKEN | Set INFLUX_TOKEN in .env |
| Connection errors | InfluxDB not running | Start InfluxDB service |
| Youless timeout | Device offline | Check Youless device network connection |
| Qingping auth fail | Invalid credentials | Verify QINGPING_APP_KEY and QINGPING_APP_SECRET |
| Vaillant auth fail | Invalid credentials | Verify MYVAILLANT_USERNAME and MYVAILLANT_PASSWORD |

### Debug Mode
Enable verbose logging:
```python
# In HomeAutomation.py, change:
logging.basicConfig(level=logging.DEBUG, ...)
```

### Test Individual Tasks
You can test individual task functions directly since they're all defined in `HomeAutomation.py`:

```python
# Import and run specific tasks
from HomeAutomation import youless_electra_task, youless_gas_task, outside_weather_task

# Run manually
youless_electra_task()
youless_gas_task()
outside_weather_task()
```

Note: These tasks require proper environment configuration (InfluxDB, API access, etc.) to run successfully.

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## Change History

| Date | Change |
|------|--------|
| 2026-10-10 | Refactored InfluxWriter to use connection pooling from HomeAutomation; Removed legacy files; Updated comprehensive documentation |
| 2025-11-30 | Updated README, adapted NestReader with Copilot |
| 2024-12-08 | Added outside weather to dashboard |
| 2024-12-04 | Added Nest thermostat monitoring (legacy, now removed) |
| 2024-12-01 | First version of Nest integration (legacy, now removed) |
| 2024-11-28 | Recreated project after Raspberry Pi crash |
