import os
import json
import time
import threading

import serial
import paho.mqtt.client as mqtt

SERIAL_PORT   = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
BAUD_RATE     = int(os.getenv("BAUD_RATE", "115200"))
MQTT_BROKER   = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
PUB_TOPIC     = os.getenv("MQTT_TOPIC_SENSOR_DATA", "sensors/arduino")
SUB_TOPIC     = os.getenv("MQTT_TOPIC_ACTUATOR",    "actuator/command")

print("[Serial-MQTT] Starting...", flush=True)

# ── Open serial port ──────────────────────────────────────────────────────────
while True:
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[Serial-MQTT] Serial port open: {SERIAL_PORT}", flush=True)
        break
    except Exception as e:
        print(f"[Serial-MQTT] Waiting for serial port: {e}", flush=True)
        time.sleep(3)

# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[Serial-MQTT] Connected to MQTT", flush=True)
        client.subscribe(SUB_TOPIC)
        print(f"[Serial-MQTT] Subscribed to {SUB_TOPIC}", flush=True)
    else:
        print(f"[Serial-MQTT] MQTT connection failed: {reason_code}", flush=True)

def on_message(client, userdata, msg):
    # Received actuator command from ml-service → forward to Arduino via serial
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        command = payload.get("command", "")

        if command == "TURN_ON":
            ser.write(b"LED_ON\n")
            print("[Serial-MQTT] Sent LED_ON to Arduino", flush=True)
        elif command == "TURN_OFF":
            ser.write(b"LED_OFF\n")
            print("[Serial-MQTT] Sent LED_OFF to Arduino", flush=True)

    except Exception as e:
        print(f"[Serial-MQTT] Error forwarding command: {e}", flush=True)

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

while True:
    try:
        print(f"[Serial-MQTT] Connecting to MQTT {MQTT_BROKER}:{MQTT_PORT}...", flush=True)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        break
    except Exception as e:
        print(f"[Serial-MQTT] Waiting for MQTT: {e}", flush=True)
        time.sleep(3)

# ── Read serial in background thread → publish to MQTT ───────────────────────
def serial_reader():
    while True:
        try:
            line = ser.readline().decode("utf-8").strip()

            if not line:
                continue

            # Only forward IMU data lines, ignore other serial output
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

                # Parse "X: 0.123 Y: 0.456 Z: 0.789 Total: 1.234"
                values = {}
                tokens = line.split()
                for i, token in enumerate(tokens):
                    if token in ("X:", "Y:", "Z:", "Total:"):
                        key = token.rstrip(":")
                        values[key] = float(tokens[i + 1])

                if len(values) == 4:
                    mqtt_client.publish(PUB_TOPIC, json.dumps(values))
                    print(f"[Serial-MQTT] Published: {values}", flush=True)

        except Exception as e:
            print(f"[Serial-MQTT] Serial read error: {e}", flush=True)
            time.sleep(1)

reader_thread = threading.Thread(target=serial_reader, daemon=True)
reader_thread.start()

# ── MQTT loop (main thread) ───────────────────────────────────────────────────
print("[Serial-MQTT] Running...", flush=True)
mqtt_client.loop_forever()