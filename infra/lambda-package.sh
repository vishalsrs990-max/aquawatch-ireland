#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
BUILD_DIR="${ROOT_DIR}/build"

rm -rf "${DIST_DIR}" "${BUILD_DIR}"
mkdir -p "${DIST_DIR}" "${BUILD_DIR}/processor" "${BUILD_DIR}/api"

python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install boto3 -t "${BUILD_DIR}/processor" >/dev/null
python3 -m pip install boto3 -t "${BUILD_DIR}/api" >/dev/null

cp "${ROOT_DIR}/backend/processor_lambda.py" "${BUILD_DIR}/processor/lambda_function.py"
cp "${ROOT_DIR}/api/dashboard_api_lambda.py" "${BUILD_DIR}/api/lambda_function.py"

(
  cd "${BUILD_DIR}/processor"
  zip -qr "${DIST_DIR}/processor_lambda.zip" .
)
(
  cd "${BUILD_DIR}/api"
  zip -qr "${DIST_DIR}/dashboard_api_lambda.zip" .
)

echo "Created: ${DIST_DIR}/processor_lambda.zip"
echo "Created: ${DIST_DIR}/dashboard_api_lambda.zip"
