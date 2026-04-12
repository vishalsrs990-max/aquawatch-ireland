import json
import math
import os
import random
import time
from datetime import datetime, timezone

import requests

FOG_URL = os.getenv("FOG_URL", "http://127.0.0.1:8000/ingest")
STATION_ID = os.getenv("STATION_ID", "dublin-liffey-01")
INTERVAL_SECONDS = float(os.getenv("INTERVAL_SECONDS", "3"))


class SensorSimulator:
    def __init__(self, station_id: str):
        self.station_id = station_id
        self.tick = 0

    def generate(self) -> dict:
        self.tick += 1
        now = datetime.now(timezone.utc).isoformat()

        seasonal = math.sin(self.tick / 8)
        rainfall = max(0.0, round(random.uniform(0, 4) + max(0, seasonal) * 18, 2))
        water_level = round(1.6 + seasonal * 0.5 + (rainfall * 0.03) + random.uniform(-0.05, 0.05), 3)
        water_temp = round(10 + math.sin(self.tick / 12) * 4 + random.uniform(-0.4, 0.4), 2)
        turbidity = round(12 + rainfall * 1.7 + random.uniform(0, 4), 2)
        flow_rate = round(22 + water_level * 8 + rainfall * 0.8 + random.uniform(-1.5, 1.5), 2)

        # rare anomaly burst for demo
        if self.tick % 30 == 0:
            rainfall = round(rainfall + 20, 2)
            water_level = round(water_level + 0.7, 3)
            turbidity = round(turbidity + 25, 2)
            flow_rate = round(flow_rate + 12, 2)

        return {
            "stationId": self.station_id,
            "timestamp": now,
            "sensors": {
                "water_level_m": water_level,
                "rainfall_mm_h": rainfall,
                "water_temp_c": water_temp,
                "turbidity_ntu": turbidity,
                "flow_rate_m3s": flow_rate,
            },
        }


def main() -> None:
    sim = SensorSimulator(STATION_ID)
    print(f"Sending data to fog node at {FOG_URL}")
    while True:
        payload = sim.generate()
        try:
            response = requests.post(FOG_URL, json=payload, timeout=10)
            print(json.dumps({
                "status_code": response.status_code,
                "response": response.json() if response.content else {},
                "sent": payload,
            }, indent=2))
        except Exception as exc:
            print(f"Error sending payload: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
