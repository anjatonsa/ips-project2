import serial
import json
import paho.mqtt.client as mqtt

# -------------------------
# Serial settings
# -------------------------
PORT = "/dev/ttyACM0"
BAUDRATE = 115200

# -------------------------
# MQTT settings
# -------------------------
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "arduino/sensors"

# Connect to Arduino
ser = serial.Serial(PORT, BAUDRATE, timeout=1)

# Connect to MQTT
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

print("Connected to Arduino!")
print("Connected to MQTT!")
print("Waiting for sensor data...")

while True:
    line = ser.readline().decode("utf-8", errors="ignore").strip()

    if not line:
        continue

    # Only process lines starting with "X:"
    if not line.startswith("X:"):
        continue

    try:
        # Example:
        # X: -0.02  Y: 0.01  Z: 0.97  Total: 0.98

        parts = line.split()

        data = {
            "X": float(parts[1]),
            "Y": float(parts[3]),
            "Z": float(parts[5]),
            "Total": float(parts[7])
        }

        # Convert to JSON
        json_data = json.dumps(data)

        print("Sending:", json_data)

        # Send to MQTT
        mqtt_client.publish(MQTT_TOPIC, json_data)

    except (ValueError, IndexError) as e:
        print("Could not parse line:", line)
        print("Error:", e)