import json
import os
import statistics
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List

from awscrt import auth, io, mqtt
from awsiot import mqtt_connection_builder
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
IOT_ENDPOINT = os.getenv("IOT_ENDPOINT", "")
MQTT_TOPIC_TEMPLATE = os.getenv("MQTT_TOPIC_TEMPLATE", "aquawatch/{station_id}/aggregated")
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "5"))

app = FastAPI(title="AquaWatch Fog Node")


class SensorValues(BaseModel):
    water_level_m: float = Field(..., ge=0, le=10)
    rainfall_mm_h: float = Field(..., ge=0, le=500)
    water_temp_c: float = Field(..., ge=-5, le=40)
    turbidity_ntu: float = Field(..., ge=0, le=5000)
    flow_rate_m3s: float = Field(..., ge=0, le=2000)


class RawPayload(BaseModel):
    stationId: str
    timestamp: str
    sensors: SensorValues


_buffers: Dict[str, Deque[dict]] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
_mqtt_connection = None
_mqtt_lock = threading.Lock()


def severity_for(values: dict) -> str:
    score = 0
    if values["water_level_m"] >= 2.4:
        score += 2
    elif values["water_level_m"] >= 2.0:
        score += 1

    if values["rainfall_mm_h"] >= 25:
        score += 2
    elif values["rainfall_mm_h"] >= 12:
        score += 1

    if values["turbidity_ntu"] >= 60:
        score += 1

    if values["flow_rate_m3s"] >= 45:
        score += 1

    if score >= 4:
        return "CRITICAL"
    if score >= 2:
        return "WARNING"
    return "NORMAL"


def aggregate(samples: List[dict]) -> dict:
    keys = [
        "water_level_m",
        "rainfall_mm_h",
        "water_temp_c",
        "turbidity_ntu",
        "flow_rate_m3s",
    ]
    averages = {
        key: round(statistics.fmean(sample[key] for sample in samples), 3)
        for key in keys
    }
    averages["severity"] = severity_for(averages)
    return averages


def get_mqtt_connection():
    global _mqtt_connection
    if _mqtt_connection is not None:
        return _mqtt_connection

    if not IOT_ENDPOINT:
        raise RuntimeError("IOT_ENDPOINT environment variable is required")

    with _mqtt_lock:
        if _mqtt_connection is not None:
            return _mqtt_connection

        event_loop_group = io.EventLoopGroup(1)
        host_resolver = io.DefaultHostResolver(event_loop_group)
        client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
        credentials_provider = auth.AwsCredentialsProvider.new_default_chain(client_bootstrap)

        connection = mqtt_connection_builder.websockets_with_default_aws_signing(
            endpoint=IOT_ENDPOINT,
            client_bootstrap=client_bootstrap,
            region=AWS_REGION,
            credentials_provider=credentials_provider,
            client_id=f"aquawatch-fog-{uuid.uuid4()}",
            clean_session=False,
            keep_alive_secs=30,
        )
        connection.connect().result()
        _mqtt_connection = connection
        return _mqtt_connection


@app.get("/health")
def health():
    return {
        "ok": True,
        "region": AWS_REGION,
        "iot_endpoint_configured": bool(IOT_ENDPOINT),
        "window_size": WINDOW_SIZE,
    }


@app.post("/ingest")
def ingest(payload: RawPayload):
    try:
        # Parse timestamp early to validate format
        datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {exc}")

    sensor_dict = payload.sensors.model_dump()
    _buffers[payload.stationId].append(sensor_dict)
    aggregated = aggregate(list(_buffers[payload.stationId]))

    outgoing = {
        "stationId": payload.stationId,
        "rawTimestamp": payload.timestamp,
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "windowSize": len(_buffers[payload.stationId]),
        "metrics": aggregated,
    }

    topic = MQTT_TOPIC_TEMPLATE.format(station_id=payload.stationId)

    try:
        mqtt_connection = get_mqtt_connection()
        mqtt_connection.publish(
            topic=topic,
            payload=json.dumps(outgoing),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MQTT publish failed: {exc}")

    return {
        "message": "Payload validated, aggregated, and published",
        "topic": topic,
        "published": outgoing,
    }
