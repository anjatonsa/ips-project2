import serial
import json
import paho.mqtt.client as mqtt
import os

PORT = "/dev/ttyACM0"
BAUDRATE = 115200

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_SENSOR_DATA = os.getenv("MQTT_TOPIC_SENSOR_DATA")

ser = serial.Serial(PORT, BAUDRATE, timeout=1)

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

print("Connected to Arduino and MQTT!")
print("Waiting for sensor data...")

while True:
    line = ser.readline().decode("utf-8", errors="ignore").strip()

    if not line:
        continue

    if not line.startswith("X:"):
        continue

    try:

        parts = line.split()

        data = {
            "X": float(parts[1]),
            "Y": float(parts[3]),
            "Z": float(parts[5]),
            "Total": float(parts[7])
        }

        json_data = json.dumps(data)

        print("Sending:", json_data)

        mqtt_client.publish(MQTT_TOPIC_SENSOR_DATA, json_data)

    except (ValueError, IndexError) as e:
        print("Could not parse line:", line)
        print("Error:", e)