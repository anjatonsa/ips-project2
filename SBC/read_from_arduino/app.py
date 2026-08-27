import os
import json
import time
import threading

import serial
import paho.mqtt.client as mqtt

SERIAL_PORT = os.getenv("SERIAL_PORT")
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC_SENSOR_DATA = os.getenv("MQTT_TOPIC_SENSOR_DATA")
MQTT_COMMAND_TOPIC = os.getenv("MQTT_COMMAND_TOPIC")

print("Serial connection with Arduino...", flush=True)
while True:
    try:
        ser = serial.Serial(SERIAL_PORT, 115200, timeout=1)
        print(f"Serial port open: {SERIAL_PORT}", flush=True)
        break
    except Exception as e:
        print(f"Waiting for serial port: {e}", flush=True)
        time.sleep(3)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT", flush=True)
        client.subscribe(MQTT_COMMAND_TOPIC)
        print(f"Subscribed to {MQTT_COMMAND_TOPIC}", flush=True)
    else:
        print(f"MQTT connection failed: {reason_code}", flush=True)

def on_message(client, userdata, msg):
    # Received actuator command from ml-service
    # forward to Arduino via serial
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        command = payload.get("command", "")

        if command == "TURN_ON":
            ser.write(b"LED_ON\n")
            print("Sent LED_ON to Arduino", flush=True)
        elif command == "TURN_OFF":
            ser.write(b"LED_OFF\n")
            print("Sent LED_OFF to Arduino", flush=True)

    except Exception as e:
        print(f"Error forwarding command: {e}", flush=True)

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

while True:
    try:
        print(f"Connecting to MQTT {MQTT_BROKER}:{MQTT_PORT}...", flush=True)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        break
    except Exception as e:
        print(f"Waiting for MQTT: {e}", flush=True)
        time.sleep(3)

def serial_reader():
    while True:
        try:
            line = ser.readline().decode("utf-8").strip()

            if not line:
                continue

            if line.startswith("X:"):
                parts = {}
                for token in line.split():
                    if token in ("X:", "Y:", "Z:", "Total:"):
                        key = token.rstrip(":")
                        # next token is the value
                for part in line.split():
                    try:
                        pass
                    except:
                        pass

                values = {}
                tokens = line.split()
                for i, token in enumerate(tokens):
                    if token in ("X:", "Y:", "Z:", "Total:"):
                        key = token.rstrip(":")
                        values[key] = float(tokens[i + 1])

                if len(values) == 4:
                    mqtt_client.publish(MQTT_TOPIC_SENSOR_DATA, json.dumps(values))
                    print(f"Published: {values}", flush=True)

        except Exception as e:
            print(f"Serial read error: {e}", flush=True)
            time.sleep(1)

reader_thread = threading.Thread(target=serial_reader, daemon=True)
reader_thread.start()

print("Running...", flush=True)
mqtt_client.loop_forever()