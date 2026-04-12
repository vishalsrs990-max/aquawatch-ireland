import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
LATEST_TABLE = os.getenv("LATEST_TABLE", "AquaLatest")
HISTORY_TABLE = os.getenv("HISTORY_TABLE", "AquaHistory")
DEFAULT_STATION = os.getenv("DEFAULT_STATION", "dublin-liffey-01")


dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
latest_tbl = dynamodb.Table(LATEST_TABLE)
history_tbl = dynamodb.Table(HISTORY_TABLE)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def response(status_code: int, body: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def extract_route(event):
    route_key = event.get("routeKey", "")
    raw_path = event.get("rawPath") or event.get("path") or "/"
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "GET"
    return route_key, raw_path, method


def lambda_handler(event, context):
    route_key, raw_path, method = extract_route(event)

    if method == "OPTIONS":
        return response(200, {"ok": True})

    params = event.get("queryStringParameters") or {}
    station_id = params.get("stationId", DEFAULT_STATION)
    limit = int(params.get("limit", "50"))

    if raw_path.endswith("/latest"):
        item = latest_tbl.get_item(Key={"stationId": station_id}).get("Item")
        return response(200, {"item": item or {}})

    if raw_path.endswith("/history"):
        result = history_tbl.query(
            KeyConditionExpression=Key("stationId").eq(station_id),
            ScanIndexForward=False,
            Limit=limit,
        )
        return response(200, {"items": result.get("Items", [])})

    if raw_path.endswith("/overview"):
        latest = latest_tbl.get_item(Key={"stationId": station_id}).get("Item") or {}
        history = history_tbl.query(
            KeyConditionExpression=Key("stationId").eq(station_id),
            ScanIndexForward=False,
            Limit=min(limit, 100),
        ).get("Items", [])
        return response(200, {
            "stationId": station_id,
            "latest": latest,
            "history": history,
        })

    return response(404, {"error": f"Route not found for path {raw_path}"})
