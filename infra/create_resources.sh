#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
QUEUE_NAME="aquawatch-queue"
LATEST_TABLE="AquaLatest"
HISTORY_TABLE="AquaHistory"

echo "Creating SQS queue: ${QUEUE_NAME}"
aws sqs create-queue --queue-name "${QUEUE_NAME}" --region "${REGION}" >/dev/null || true

echo "Creating DynamoDB table: ${LATEST_TABLE}"
aws dynamodb create-table \
  --table-name "${LATEST_TABLE}" \
  --attribute-definitions AttributeName=stationId,AttributeType=S \
  --key-schema AttributeName=stationId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" >/dev/null || true

echo "Creating DynamoDB table: ${HISTORY_TABLE}"
aws dynamodb create-table \
  --table-name "${HISTORY_TABLE}" \
  --attribute-definitions AttributeName=stationId,AttributeType=S AttributeName=ts,AttributeType=S \
  --key-schema AttributeName=stationId,KeyType=HASH AttributeName=ts,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" >/dev/null || true

echo "Waiting for tables to become ACTIVE..."
aws dynamodb wait table-exists --table-name "${LATEST_TABLE}" --region "${REGION}" || true
aws dynamodb wait table-exists --table-name "${HISTORY_TABLE}" --region "${REGION}" || true

echo "Done."
aws sqs get-queue-url --queue-name "${QUEUE_NAME}" --region "${REGION}"
