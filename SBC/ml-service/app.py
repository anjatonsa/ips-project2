import json
import os
import pickle
import time
from collections import deque

import numpy as np
import paho.mqtt.client as mqtt
import tflite_runtime.interpreter as tflite

# ── Config ────────────────────────────────────────────────────────────────────
MQTT_BROKER   = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_CONFIG = os.getenv("MQTT_TOPIC_CONFIG")
SUB_TOPIC     = os.getenv("MQTT_TOPIC_SENSOR_DATA")
PUB_TOPIC     = os.getenv("MQTT_COMMAND_TOPIC")

WINDOW_SIZE   = 4     # must match training — 1 second at 4Hz
N_FEATURES    = 3     # X, Y, Z
THRESHOLD     = 0.5   # probability above this = vibration anomaly

MODEL_PATH    = "/app/model.tflite"
SCALER_PATH   = "/app/scaler.json"

print("[ML] Loading TFLite model...", flush=True)
interpreter = tflite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

input_idx  = input_details[0]["index"]
output_idx = output_details[0]["index"]

print(f"[ML] Input shape  : {input_details[0]['shape']}", flush=True)
print(f"[ML] Output shape : {output_details[0]['shape']}", flush=True)

with open(SCALER_PATH, "r") as f:
    scaler_params = json.load(f)

scaler_mean  = np.array(scaler_params["mean"],  dtype=np.float32)
scaler_scale = np.array(scaler_params["scale"], dtype=np.float32)

def apply_scaler(window):
    # Replicate StandardScaler: (x - mean) / scale
    return (window - scaler_mean) / scaler_scale
print("[ML] Model and scaler loaded", flush=True)

# ── Rolling buffer ────────────────────────────────────────────────────────────
buffer = deque(maxlen=WINDOW_SIZE)

# Track consecutive anomalies to avoid spamming the actuator
consecutive_anomalies  = 0
consecutive_normal     = 0
ANOMALY_TRIGGER_COUNT  = 2   # fire actuator after this many consecutive anomaly windows
NORMAL_RESET_COUNT     = 3   # reset after this many consecutive normal windows
actuator_active        = False

def run_inference():
    raw    = np.array(buffer, dtype=np.float32)   # (4, 4)
    scaled = apply_scaler(raw)                     # (4, 4)
    inp    = scaled.reshape(1, WINDOW_SIZE, N_FEATURES).astype(np.float32)

    interpreter.set_tensor(input_idx, inp)
    interpreter.invoke()

    prob = float(interpreter.get_tensor(output_idx)[0][0])
    return prob

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[ML] Connected to MQTT broker", flush=True)

        client.subscribe(SUB_TOPIC)
        print(f"[ML] Subscribed to {SUB_TOPIC}", flush=True)

        client.subscribe(MQTT_TOPIC_CONFIG)
        print(f"[ML] Subscribed to {MQTT_TOPIC_CONFIG}", flush=True)

    else:
        print(f"[ML] MQTT connection failed: {reason_code}", flush=True)

def on_message(client, userdata, msg):
    global consecutive_anomalies, consecutive_normal, actuator_active

    global THRESHOLD

    if msg.topic == MQTT_TOPIC_CONFIG:
        try:
            payload = json.loads(msg.payload.decode())
            new_threshold = float(payload.get("threshold", THRESHOLD))
            THRESHOLD = new_threshold
            print(f"[ML] Threshold updated to {THRESHOLD}", flush=True)
        except Exception as e:
            print(f"[ML] Config error: {e}", flush=True)
        return
    
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        x = float(payload["X"])
        y = float(payload["Y"])
        z = float(payload["Z"])

        buffer.append([x, y, z])

        if len(buffer) < WINDOW_SIZE:
            print(f"[ML] Buffering {len(buffer)}/{WINDOW_SIZE}...", flush=True)
            return

        prob  = run_inference()
        label = 1 if prob >= THRESHOLD else 0
        print(f"Prob={prob:.4f} buffer={list(buffer)}", flush=True)

        print(
            f"Prob={prob:.3f} → {'movement' if label else 'normal'}",
            flush=True
        )

        # ── Actuator logic
        if label == 1:
            consecutive_anomalies += 1
            consecutive_normal     = 0

            # Only trigger actuator once when threshold is first crossed
            if consecutive_anomalies >= ANOMALY_TRIGGER_COUNT and not actuator_active:
                actuator_active = True
                command = json.dumps({
                    "command":    "TURN_ON",
                    "reason":     "sustained_vibration",
                    "confidence": round(prob, 3)
                })
                client.publish(PUB_TOPIC, command)
                print(f"Anomaly confirmed — published TURN_ON to {PUB_TOPIC}", flush=True)

        else:
            consecutive_normal    += 1
            consecutive_anomalies  = 0

            # Turn off actuator once movement has clearly stopped
            if consecutive_normal >= NORMAL_RESET_COUNT and actuator_active:
                actuator_active = False
                command = json.dumps({
                    "command": "TURN_OFF",
                    "reason":  "vibration_stopped"
                })
                client.publish(PUB_TOPIC, command)
                print(f"[ML] Vibration stopped — published TURN_OFF to {PUB_TOPIC}", flush=True)

    except KeyError as e:
        print(f"[ML] Missing field in payload: {e}", flush=True)
    except Exception as e:
        print(f"[ML] Error: {e}", flush=True)

# ── MQTT client setup ─────────────────────────────────────────────────────────
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

# ── Wait for broker ───────────────────────────────────────────────────────────
while True:
    try:
        print(f"[ML] Connecting to {MQTT_BROKER}:{MQTT_PORT}...", flush=True)
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        break
    except Exception as e:
        print(f"[ML] Waiting for MQTT broker: {e}", flush=True)
        time.sleep(3)

print("[ML] Starting loop...", flush=True)
client.loop_forever()