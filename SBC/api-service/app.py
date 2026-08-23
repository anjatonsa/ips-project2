import asyncio
import json
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient

# ── Config ────────────────────────────────────────────────────────────────────
MQTT_BROKER         = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT           = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_SENSOR   = os.getenv("MQTT_TOPIC_SENSOR_DATA", "sensors/arduino")
MQTT_TOPIC_ACTUATOR = os.getenv("MQTT_TOPIC_ACTUATOR",    "actuator/command")
MQTT_TOPIC_CONFIG   = os.getenv("MQTT_TOPIC_CONFIG",      "ml/config")

INFLUX_URL    = os.getenv("INFLUX_URL",    "http://influxdb:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN")
INFLUX_ORG    = os.getenv("INFLUX_ORG",    "ips")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "acceleration_data")

# ── State ─────────────────────────────────────────────────────────────────────
connected_clients: list[WebSocket] = []
recent_events: deque = deque(maxlen=50)   # last 50 anomaly events
current_threshold: float = 0.5
latest_sensor: dict = {}

# ── MQTT setup ────────────────────────────────────────────────────────────────
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[API] MQTT connected", flush=True)
        client.subscribe(MQTT_TOPIC_SENSOR)
        client.subscribe(MQTT_TOPIC_ACTUATOR)
    else:
        print(f"[API] MQTT failed: {reason_code}", flush=True)

def on_mqtt_message(client, userdata, msg):
    global latest_sensor
    try:
        payload = json.loads(msg.payload.decode())

        if msg.topic == MQTT_TOPIC_SENSOR:
            latest_sensor = payload

        elif msg.topic == MQTT_TOPIC_ACTUATOR:
            # Anomaly event — store and broadcast to all WebSocket clients
            event = {
                "type":      "anomaly",
                "command":   payload.get("command"),
                "reason":    payload.get("reason"),
                "confidence": payload.get("confidence"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            recent_events.appendleft(event)
            asyncio.run(broadcast(json.dumps(event)))

    except Exception as e:
        print(f"[API] MQTT message error: {e}", flush=True)

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message

# ── Broadcast to all WebSocket clients ────────────────────────────────────────
async def broadcast(message: str):
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)

# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect MQTT on startup
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("[API] Started", flush=True)
    yield
    mqtt_client.loop_stop()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    print(f"[API] WS client connected. Total: {len(connected_clients)}", flush=True)

    # Send last 10 events immediately on connect so app has context
    for event in list(recent_events)[:10]:
        await websocket.send_text(json.dumps(event))

    try:
        while True:
            # Keep connection alive — send ping every 30s
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print(f"[API] WS client disconnected. Total: {len(connected_clients)}", flush=True)

# ── REST: sensor data from InfluxDB ──────────────────────────────────────────
@app.get("/api/sensors")
def get_sensors(minutes: int = 10):
    try:
        client = InfluxDBClient(
            url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG
        )
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "sensor_data")
          |> filter(fn: (r) => r._field == "X" or r._field == "Y" or r._field == "Z")
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> keep(columns: ["_time", "X", "Y", "Z"])
          |> sort(columns: ["_time"])
        '''
        df = client.query_api().query_data_frame(query)
        if df.empty:
            return {"data": []}

        df["_time"] = df["_time"].astype(str)
        return {"data": df[["_time", "X", "Y", "Z"]].to_dict(orient="records")}
    except Exception as e:
        return {"error": str(e), "data": []}

# ── REST: latest sensor reading ───────────────────────────────────────────────
@app.get("/api/sensors/latest")
def get_latest_sensor():
    return {"data": latest_sensor}

# ── REST: recent anomaly events ───────────────────────────────────────────────
@app.get("/api/events")
def get_events():
    return {"events": list(recent_events)}

# ── REST: current ML threshold ────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    return {"threshold": current_threshold}

# ── REST: update ML threshold ─────────────────────────────────────────────────
@app.post("/api/config/threshold")
def set_threshold(body: dict):
    global current_threshold
    value = float(body.get("threshold", 0.5))

    if not 0.0 < value < 1.0:
        return {"error": "Threshold must be between 0 and 1"}

    current_threshold = value
    mqtt_client.publish(
        MQTT_TOPIC_CONFIG,
        json.dumps({"threshold": current_threshold})
    )
    print(f"[API] Threshold updated to {current_threshold}", flush=True)
    return {"threshold": current_threshold}

# ── REST: trigger actuator manually ──────────────────────────────────────────
@app.post("/api/actuator")
def control_actuator(body: dict):
    command = body.get("command", "TURN_ON")
    if command not in ("TURN_ON", "TURN_OFF"):
        return {"error": "command must be TURN_ON or TURN_OFF"}

    mqtt_client.publish(
        MQTT_TOPIC_ACTUATOR,
        json.dumps({"command": command, "reason": "manual_app_trigger"})
    )
    print(f"[API] Actuator command: {command}", flush=True)
    return {"command": command, "status": "sent"}

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}