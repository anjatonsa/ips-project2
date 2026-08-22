import os
import json
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, SYNCHRONOUS

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_SENSOR_DATA = os.getenv("MQTT_TOPIC_SENSOR_DATA")

INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
INFLUX_ORG = os.getenv("INFLUX_ORG", "ips")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "acceleration_data")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")


print("Starting MQTT → InfluxDB service...", flush=True)


while True:
    try:
        influx_client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG
        )

        if influx_client.ping():
            print("Connected to InfluxDB", flush=True)
            break

        print("InfluxDB is not ready yet", flush=True)

    except Exception as e:
        print("Waiting for InfluxDB:", e, flush=True)

    time.sleep(3)


write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"MQTT connection result: {reason_code}", flush=True)

    if reason_code == 0:
        print("Connected to MQTT", flush=True)

        client.subscribe(MQTT_TOPIC_SENSOR_DATA)

        print(
            f"Subscribed to topic: {MQTT_TOPIC_SENSOR_DATA}",
            flush=True
        )


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        print(f"Received: {payload}", flush=True)

        point = Point("sensor_data")

        has_fields = False
        for key, value in data.items():
            if isinstance(value, (int, float)):
                point.field(key, float(value))
                has_fields = True

        if not has_fields:
            print("No numeric fields found, skipping", flush=True)
            return

        write_api.write(
            bucket=INFLUX_BUCKET,
            org=INFLUX_ORG,
            record=point
        )

        print("Written to InfluxDB", flush=True)

    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


while True:

    try:

        print(
            f"Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT}...",
            flush=True
        )

        mqtt_client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            60
        )

        break

    except Exception as e:

        print(
            f"Waiting for MQTT: {e}",
            flush=True
        )

        time.sleep(3)


print("Starting MQTT loop...", flush=True)

mqtt_client.loop_forever()