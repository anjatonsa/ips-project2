# README – Initial Setup and Startup Guide

## Prerequisites

Before starting the application, make sure the following software is installed:

* Docker Desktop (Windows) or Docker Engine (Linux)
* Docker Compose
* Internet connection for downloading Docker images

Verify the installation:

```bash
docker --version
docker compose version
```

---

## Project Structure

```text
iot-project/
├── docker-compose.yml
├── .env
├── mosquitto/
│   └── config/
│       └── mosquitto.conf
├── mqtt-to-influx/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
└── grafana/
```

---

## Step 1 – Configure Environment Variables

Create a file named `.env` in the project root directory.

Initially, insert:

```env
INFLUX_TOKEN=CHANGE_THIS_AFTER_SETUP
```

The actual token will be generated during the InfluxDB initialization process.

---

## Step 2 – Start Mosquitto and InfluxDB

From the project root directory execute:

```bash
docker compose up -d mosquitto influxdb
```

Verify that both containers are running:

```bash
docker ps
```

Expected containers:

```text
mosquitto
influxdb
```

---

## Step 3 – Initialize InfluxDB

Open a web browser and navigate to:

```text
http://localhost:8086
```

Complete the initial setup:

| Parameter    | Value        |
| ------------ | ------------ |
| Username     | admin        |
| Password     | user-defined |
| Organization | iot          |
| Bucket       | sensor_data  |

After the setup is completed:

1. Navigate to **Load Data → API Tokens**
2. Create an API token with read/write permissions for the bucket
3. Copy the generated token

---

## Step 4 – Update Environment Variables

Open the `.env` file and replace:

```env
INFLUX_TOKEN=CHANGE_THIS_AFTER_SETUP
```

with:

```env
INFLUX_TOKEN=<generated_token>
```

Save the file.

---

## Step 5 – Start MQTT-to-InfluxDB Service

Build and start the service:

```bash
docker compose up -d mqtt-to-influx
```

Verify container status:

```bash
docker ps
```

Check application logs:

```bash
docker logs mqtt-to-influx
```

Expected output:

```text
Starting MQTT → InfluxDB service...
Connected to InfluxDB
Connected to MQTT
Subscribed to sensors/arduino
```

---

## Step 6 – Start Grafana

Start Grafana:

```bash
docker compose up -d grafana
```

Verify container status:

```bash
docker ps
```

Expected additional container:

```text
grafana
```

---

## Step 7 – Configure Grafana

Open:

```text
http://localhost:3000
```

Default credentials:

```text
Username: admin
Password: admin
```

Grafana will request a password change during the first login.

---

## Step 8 – Add InfluxDB Data Source

In Grafana:

1. Open **Connections**
2. Select **Data Sources**
3. Click **Add Data Source**
4. Choose **InfluxDB**

Configuration:

```text
URL: http://influxdb:8086
Query Language: Flux
Organization: iot
Default Bucket: sensor_data
Token: <generated_token>
```

Click:

```text
Save & Test
```

A successful connection message should be displayed.

---

## Step 9 – Verify the Complete Stack

Check that all containers are running:

```bash
docker ps
```

Expected services:

```text
mosquitto
influxdb
mqtt-to-influx
grafana
```

View logs if necessary:

```bash
docker logs mosquitto
docker logs influxdb
docker logs mqtt-to-influx
docker logs grafana
```

---

## Stopping the Application

To stop all services:

```bash
docker compose down
```

---

## Restarting the Application

To start all services after initial configuration:

```bash
docker compose up -d
```

Verify status:

```bash
docker ps
```

All containers should return to the running state automatically.
