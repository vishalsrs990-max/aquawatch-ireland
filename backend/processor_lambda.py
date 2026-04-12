import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
LATEST_TABLE = os.getenv("LATEST_TABLE", "AquaLatest")
HISTORY_TABLE = os.getenv("HISTORY_TABLE", "AquaHistory")


dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
latest_tbl = dynamodb.Table(LATEST_TABLE)
history_tbl = dynamodb.Table(HISTORY_TABLE)


def to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value


def lambda_handler(event, context):
    processed = []
    for record in event.get("Records", []):
        body = record.get("body", "{}")
        payload = json.loads(body)

        station_id = payload["stationId"]
        processed_at = payload.get("processedAt") or datetime.now(timezone.utc).isoformat()
        metrics = payload.get("metrics", {})
        severity = metrics.get("severity", "NORMAL")

        latest_item = {
            "stationId": station_id,
            "ts": processed_at,
            "severity": severity,
            "windowSize": int(payload.get("windowSize", 1)),
            "metrics": to_decimal(metrics),
        }

        history_item = {
            "stationId": station_id,
            "ts": processed_at,
            "rawTimestamp": payload.get("rawTimestamp", processed_at),
            "severity": severity,
            "windowSize": int(payload.get("windowSize", 1)),
            "metrics": to_decimal(metrics),
        }

        latest_tbl.put_item(Item=latest_item)
        history_tbl.put_item(Item=history_item)

        processed.append({
            "stationId": station_id,
            "ts": processed_at,
            "severity": severity,
        })

    return {
        "statusCode": 200,
        "body": json.dumps({"processed": processed}),
    }
