# IoT System for Voice Control and ML-Based Vibration Detection

IoT system developed using **Arduino Nano 33 BLE Sense Lite** and **Raspberry Pi** for voice-activated sensor monitoring and machine-learning-based movement detection.

The system uses the Arduino's **LSM9DS1 IMU accelerometer** to collect X, Y and Z acceleration data. After the system is activated using a voice command, sensor data is sent to the Raspberry Pi and distributed through an MQTT broker. The data is stored in InfluxDB, while a TensorFlow Lite model running on the Raspberry Pi analyzes the accelerometer data and detects movement events.

When a movement event is detected, the ML service sends an MQTT command that is forwarded to the Arduino and used to activate an LED.

---

# Technologies

## Hardware

* Arduino Nano 33 BLE Sense Lite
* Raspberry Pi 4
* LSM9DS1 IMU / accelerometer

## Software

* Python
* Docker
* Docker Compose
* Mosquitto MQTT
* InfluxDB
* Grafana
* TensorFlow
* TensorFlow Lite
* NumPy
* Pandas
* Scikit-learn
* PySerial
* Paho MQTT

---

# Main Components

## Arduino Nano 33 BLE Sense Lite

The Arduino is responsible for collecting sensor data and activating the system using a voice command.

The LSM9DS1 IMU provides accelerometer measurements along three axes.

The Arduino sends the measurements through a serial connection to the Raspberry Pi.

The Arduino also receives actuator commands from the Raspberry Pi. In the current implementation, the actuator is simulated using an LED.

---

## read_from_arduino

`read_from_arduino` is a helper Python service that acts as a communication bridge between the Arduino and the MQTT infrastructure.

Its responsibilities are:

* establish a serial connection with Arduino,
* read accelerometer measurements,
* parse X, Y and Z values,
* convert sensor data to JSON,
* publish sensor data to MQTT,
* subscribe to actuator commands,
* forward MQTT commands to Arduino through the serial connection.

Example sensor message:

```json
{
    "X": 0.12,
    "Y": 0.05,
    "Z": 0.98
}
```

The service also forwards commands such as:

```text
LED_ON
LED_OFF
```

to the Arduino.

---

## Mosquitto MQTT Broker

Mosquitto is used as the central MQTT broker.

The system uses MQTT's publish/subscribe communication model to exchange messages between services.

The sensor data is published to:

```text
sensors/arduino
```

ML actuator commands are sent through the configured command topic.

MQTT allows the individual services to communicate without being directly dependent on each other.

---

## mqtt-to-influx

The `mqtt-to-influx` service subscribes to the sensor MQTT topic.

Its responsibilities are:

1. receive sensor data from MQTT,
2. parse the JSON message,
3. add the appropriate timestamp,
4. write the data to InfluxDB.

The stored data contains:

```text
_time
X
Y
Z
```

---

## InfluxDB

InfluxDB is used as the time-series database.

The main bucket is:

```text
sensor_data
```

Sensor measurements are stored together with their timestamps.

---

## Grafana

Grafana is used to visualize the accelerometer data stored in InfluxDB.

The InfluxDB data source uses:

```text
URL: http://influxdb:8086
Query Language: Flux
Organization: iot
Bucket: sensor_data
```

Example Grafana Flux query:

```flux
from(bucket: "sensor_data")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> pivot(
      rowKey: ["_time"],
      columnKey: ["_field"],
      valueColumn: "_value"
  )
  |> keep(columns: ["_time", "X", "Y", "Z"])
```

---

# Machine Learning

The ML component is responsible for detecting movement from accelerometer data.

The model uses three features:

```text
X
Y
Z
```

The classification problem contains two classes:

```text
0 → normal
1 → movement
```

---

## Data Collection

Sensor data is collected from the Arduino and stored in InfluxDB.

Separate recordings are created for:

* normal 
* movement

The data can later be exported from InfluxDB to CSV files.

---

# ML Data Preparation

## 1. Export Data from InfluxDB

The `export_influx.py` script is used to export the collected sensor data from InfluxDB into CSV format.

The resulting CSV files are used as input for the preprocessing pipeline.

---

## 2. Transform Data

Each recording is converted into the required wide format and assigned a class label, and creates fixed-size temporal windows.

```bash
    python  procces_data.py  ./transformed ./collected/movement.csv 1 ./collected/normal.csv 0                                    
```
---

The data is split into:

```text
80% → training
20% → testing
```

before windowing.

The script generates:

```text
X_train.npy
X_test.npy
y_train.npy
y_test.npy
```

---

# ML Model Training

The model is implemented using TensorFlow/Keras.

The input shape is:

```text
4 × 3
```

representing:

```text
4 time samples × 3 accelerometer features
```

The model architecture uses 1D convolutional layers:

```text
Input
  ↓
Conv1D(32)
  ↓
Conv1D(16)
  ↓
GlobalAveragePooling1D
  ↓
Dense(16)
  ↓
Dropout(0.3)
  ↓
Dense(1, sigmoid)
```

A `StandardScaler` is used to standardize X, Y and Z values before training.

The scaler parameters are saved to:

```text
scaler.json
```

This is important because the same scaling parameters must be applied to new sensor data before inference on the Raspberry Pi.

The model is trained using:

```text
Optimizer: Adam
Loss: Binary Crossentropy
Batch size: 16
Maximum epochs: 30
```

Early stopping is used to stop training when validation loss no longer improves.

The trained Keras model is saved as:

```text
model.keras
```

---

# TensorFlow Lite Conversion

The trained Keras model is converted into TensorFlow Lite format using:

```bash
python convert_tflite.py
```

The resulting file is:

```text
model.tflite
```

The TensorFlow Lite model expects:

```text
Input shape: [1, 4, 3]
Output shape: [1, 1]
```

The model uses a sigmoid output for binary classification.

The current classification threshold is:

```text
output < 0.8  → normal
output ≥ 0.8 → movement
```

The TFLite model and scaler are then copied to the Raspberry Pi:

```text
model.tflite
scaler.json
```

---

# ML Service on Raspberry Pi

The `ml-service` runs the TensorFlow Lite model on the Raspberry Pi.

Its processing pipeline is:

```text
MQTT sensor data
       ↓
X, Y, Z
       ↓
Create window of 4 samples
       ↓
Apply scaler.json
       ↓
TensorFlow Lite inference
       ↓
Classification
       ↓
normal / vibration
```

If vibration is detected, the ML service publishes an MQTT actuator command.

The command is received by `read_from_arduino`, which forwards it to the Arduino through the serial connection.

The Arduino then activates the LED, simulating an actuator.

---


# Initial Setup

# Environment Variables

Create a `.env` file in the project root.

Example:

```env
INFLUX_TOKEN=CHANGE_THIS_AFTER_SETUP

MQTT_BROKER=mosquitto
MQTT_PORT=1883

MQTT_TOPIC_SENSOR_DATA=sensors/arduino
MQTT_COMMAND_TOPIC=actuator/command

SERIAL_PORT=/dev/ttyACM0
```

The exact serial port depends on the operating system and Arduino connection.

For example:

```text
Linux:
 /dev/ttyACM0

Windows:
 COM5
```

---

# Starting the Application

## 1. Start Mosquitto and InfluxDB

```bash
docker compose up -d mosquitto influxdb
```

Check running containers:

```bash
docker ps
```

Expected:

```text
mosquitto
influxdb
```

---

## 2. Initialize InfluxDB

Open:

```text
http://localhost:8086
```

Create the initial configuration.

Recommended values:

```text
Username: admin
Password: <user-defined>
Organization: iot
Bucket: sensor_data
```

Create an API token with read/write permissions for the bucket.

Copy the generated token.

---

## 3. Update `.env`

Replace:

```env
INFLUX_TOKEN=CHANGE_THIS_AFTER_SETUP
```

with:

```env
INFLUX_TOKEN=<generated_token>
```

---

## 4. Start MQTT-to-InfluxDB

```bash
docker compose up -d mqtt-to-influx
```

Check logs:

```bash
docker logs mqtt-to-influx
```

Expected output should indicate:

```text
Starting MQTT → InfluxDB service...
Connected to InfluxDB
Connected to MQTT
Subscribed to sensors/arduino
```

---

## 5. Start the Arduino Communication Service

Connect the Arduino to the Raspberry Pi and make sure the configured serial port is correct.

Start:

```bash
docker compose up -d read_from_arduino
```

Check:

```bash
docker logs read_from_arduino
```

The service should establish the serial connection and MQTT connection.

---

## 6. Start ML Service

After copying the trained model and scaler to the ML service:

```text
ml-service/
├── model.tflite
└── scaler.json
```

start the service:

```bash
docker compose up -d ml-service
```

Check:

```bash
docker logs ml-service
```

---

## 7. Start Grafana

```bash
docker compose up -d grafana
```

Open:

```text
http://localhost:3000
```

Log in using the configured Grafana credentials.

---

# Grafana Configuration

Add an InfluxDB data source.

Use:

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

The connection should be successful.

---