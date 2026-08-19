import os
import json
import time

import numpy as np
import paho.mqtt.client as mqtt
import tensorflow as tf


MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

INPUT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "sensors/arduino"
)

OUTPUT_TOPIC = os.getenv(
    "MQTT_COMMAND_TOPIC",
    "actuator/command"
)


print("Starting ML service...", flush=True)


# --------------------------------------------------
# Temporary demonstration model
# --------------------------------------------------
#
# This model expects:
#
# [temperature, light]
#
# and produces:
#
# 0 = normal
# 1 = anomaly
#
# For now we use a simple TensorFlow model.
# Later this will be replaced with our trained
# TensorFlow Lite model.
# --------------------------------------------------

model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(2,)),
    tf.keras.layers.Dense(8, activation="relu"),
    tf.keras.layers.Dense(1, activation="sigmoid")
])

model.compile(
    optimizer="adam",
    loss="binary_crossentropy"
)

print("ML model initialized", flush=True)


# --------------------------------------------------
# MQTT
# --------------------------------------------------

def on_connect(client, userdata, flags, reason_code, properties):

    print(
        f"Connected to MQTT: {reason_code}",
        flush=True
    )

    client.subscribe(INPUT_TOPIC)

    print(
        f"Subscribed to {INPUT_TOPIC}",
        flush=True
    )


def on_message(client, userdata, msg):

    try:

        payload = msg.payload.decode()

        print(
            f"Received sensor data: {payload}",
            flush=True
        )

        data = json.loads(payload)

        temperature = float(
            data["temperature"]
        )

        light = float(
            data["light"]
        )

        # Normalize values approximately
        features = np.array([
            temperature / 50.0,
            light / 1000.0
        ], dtype=np.float32)

        features = features.reshape(1, 2)

        prediction = model.predict(
            features,
            verbose=0
        )[0][0]

        print(
            f"ML prediction: {prediction:.4f}",
            flush=True
        )

        # Temporary demonstration threshold
        if prediction > 0.5:

            command = {
                "event": "anomaly_detected",
                "temperature": temperature,
                "light": light,
                "prediction": float(prediction)
            }

            client.publish(
                OUTPUT_TOPIC,
                json.dumps(command)
            )

            print(
                "ANOMALY DETECTED → actuator command sent",
                flush=True
            )

        else:

            print(
                "Normal sensor data",
                flush=True
            )

    except Exception as e:

        print(
            f"ML processing error: {e}",
            flush=True
        )


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.on_connect = on_connect
client.on_message = on_message


# --------------------------------------------------
# Connect to MQTT
# --------------------------------------------------

while True:

    try:

        print(
            f"Connecting to MQTT {MQTT_BROKER}:{MQTT_PORT}...",
            flush=True
        )

        client.connect(
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


print("Starting ML MQTT loop...", flush=True)

client.loop_forever()