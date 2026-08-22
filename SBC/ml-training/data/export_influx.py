# export_influx.py

from influxdb_client import InfluxDBClient
import pandas as pd
import sys

INFLUX_URL = "http://<raspberry-pi-ip>:8086"
INFLUX_TOKEN = "<your-token>"
INFLUX_ORG = "ips"
INFLUX_BUCKET = "sensor_data"

if len(sys.argv) != 4:
    print("Usage:")
    print("python export_influx.py <start_time> <end_time> <output_file>")
    print()
    print("Example:")
    print("python export_influx.py 2026-08-20T10:00:00Z 2026-08-20T10:30:00Z walking_01.csv")
    sys.exit(1)

start_time = sys.argv[1]
end_time = sys.argv[2]
output_file = sys.argv[3]

client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

query_api = client.query_api()

query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: time(v: "{start_time}"), stop: time(v: "{end_time}"))
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["_time", "x", "y", "z"])
'''

print(f"Querying data from {start_time} to {end_time}...")

df = query_api.query_data_frame(query)

for col in ["result", "table"]:
    if col in df.columns:
        df = df.drop(columns=[col])

df.to_csv(output_file, index=False)

print(f"Exported {len(df)} rows to {output_file}")