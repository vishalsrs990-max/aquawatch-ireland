# AquaWatch Ireland

A lab-friendly IoT flood monitoring project for Dublin that combines:

- **Sensor simulator** (5 sensor types)
- **Fog node** (validation + aggregation)
- **AWS IoT Core with MQTT over WebSockets**
- **Amazon SQS** for decoupling
- **AWS Lambda** for processing
- **Amazon DynamoDB** for latest + history
- **API Gateway + Lambda** for dashboard APIs
- **Elastic Beanstalk** for the web dashboard
- **GitHub Actions** for CI/CD to Elastic Beanstalk

## 1) Architecture

```
Sensor Simulator
      |
      v
Fog Node (FastAPI in Cloud9)
  - validate
  - aggregate
  - severity rules
      |
      | MQTT over WSS
      v
AWS IoT Core topic: aquawatch/{stationId}/aggregated
      |
      v
IoT Rule --> SQS queue (aquawatch-queue)
      |
      v
Lambda processor --> DynamoDB
                  --> AquaLatest
                  --> AquaHistory
      |
      +--> API Lambda <-- API Gateway HTTP API
                              |
                              v
                    Elastic Beanstalk Dashboard
```

## 2) Sensor types used

1. water_level_m
2. rainfall_mm_h
3. water_temp_c
4. turbidity_ntu
5. flow_rate_m3s

## 3) Important IAM note for your LabRole

Do **not** hardcode the role ARN inside Python code.

Your code should use the **default AWS credential chain**. Because Cloud9 and Elastic Beanstalk EC2 instances run with an attached instance profile, `boto3` and the AWS IoT SDK automatically pick up temporary credentials from the role attached to the instance.

For your lab:

- **Role ARN**: `arn:aws:iam::386741940758:role/LabRole`
- **Instance Profile ARN**: `arn:aws:iam::386741940758:instance-profile/LabInstanceProfile`

Use them like this:

- **Cloud9**: the instance should already run with `LabRole`
- **Elastic Beanstalk EC2 instance profile**: choose **LabInstanceProfile** when creating the environment
- **Application code**: no access keys, no secret keys, no role ARN hardcoded

## 4) Recommended AWS resources

- Region: `us-east-1`
- IoT topic: `aquawatch/+/aggregated`
- SQS queue: `aquawatch-queue`
- DynamoDB latest table: `AquaLatest`
- DynamoDB history table: `AquaHistory`
- Lambda processor: `aquawatch-processor`
- Lambda API: `aquawatch-api`
- EB application: `aquawatch-dashboard`
- EB environment: `aquawatch-dashboard-env`

## 5) Cloud9 setup

```bash
cd ~/environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Install all dependencies for local development:

```bash
pip install -r requirements-dev.txt
```

## 6) File layout

```text
.
├── README.md
├── requirements-dev.txt
├── simulator/
│   └── sensor_simulator.py
├── fog/
│   └── fog_node.py
├── backend/
│   └── processor_lambda.py
├── api/
│   └── dashboard_api_lambda.py
├── dashboard/
│   ├── application.py
│   ├── requirements.txt
│   ├── Procfile
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── infra/
│   ├── create_resources.sh
│   ├── lambda-package.sh
│   ├── iot_rule.sql
│   └── sample_env.txt
└── .github/
    └── workflows/
        └── deploy-eb.yml
```

## 7) Step-by-step deployment

### Step A — Verify your lab credentials

```bash
aws sts get-caller-identity
```

You should see account `386741940758`.

### Step B — Create DynamoDB + SQS

```bash
chmod +x infra/create_resources.sh
./infra/create_resources.sh
```

### Step C — Get AWS IoT endpoint

```bash
aws iot describe-endpoint --endpoint-type iot:Data-ATS
```

Copy the `endpointAddress` and export it:

```bash
export AWS_REGION=us-east-1
export IOT_ENDPOINT=YOUR_ENDPOINT_HERE
```

### Step D — Create IoT Rule

Use the AWS Console:

1. Open **AWS IoT Core**
2. Go to **Message routing** → **Rules**
3. Create rule name: `aquawatch-sqs-rule`
4. SQL:

```sql
SELECT * FROM 'aquawatch/+/aggregated'
```

5. Action: **Send a message to an SQS queue**
6. Queue: `aquawatch-queue`
7. Use an existing role if your lab provides one for IoT actions; if the lab blocks new roles, use the pre-provisioned role allowed by the lab.

### Step E — Deploy Lambda processor

1. Zip the processor code:

```bash
chmod +x infra/lambda-package.sh
./infra/lambda-package.sh
```

2. In Lambda console, create function `aquawatch-processor`
3. Runtime: Python 3.11
4. Role: select a lab-allowed execution role
5. Upload `dist/processor_lambda.zip`
6. Set env vars:
   - `LATEST_TABLE=AquaLatest`
   - `HISTORY_TABLE=AquaHistory`
7. Add **SQS trigger** from `aquawatch-queue`

### Step F — Deploy API Lambda + API Gateway

1. Create Lambda function `aquawatch-api`
2. Upload `dist/dashboard_api_lambda.zip`
3. Env vars:
   - `LATEST_TABLE=AquaLatest`
   - `HISTORY_TABLE=AquaHistory`
4. Create an **HTTP API** in API Gateway and integrate it with `aquawatch-api`
5. Add routes:
   - `GET /latest`
   - `GET /history`
   - `GET /overview`
6. Enable CORS for your EB dashboard URL

### Step G — Run fog node in Cloud9

```bash
export AWS_REGION=us-east-1
export IOT_ENDPOINT=YOUR_ENDPOINT_HERE
export MQTT_TOPIC_TEMPLATE='aquawatch/{station_id}/aggregated'
uvicorn fog.fog_node:app --host 0.0.0.0 --port 8000 --reload
```

### Step H — Run simulator in Cloud9

In another terminal:

```bash
export FOG_URL=http://127.0.0.1:8000/ingest
python simulator/sensor_simulator.py
```

### Step I — Test the pipeline

Check:

- IoT test client shows published messages
- SQS queue receives messages
- Lambda processor writes to `AquaLatest` and `AquaHistory`
- API `/overview?stationId=dublin-liffey-01` returns JSON

### Step J — Deploy dashboard to Elastic Beanstalk

From the `dashboard/` folder:

1. Create EB application `aquawatch-dashboard`
2. Environment name: `aquawatch-dashboard-env`
3. Platform: Python 3.11
4. **EC2 instance profile**: select `LabInstanceProfile`
5. Add environment variable:
   - `DASHBOARD_API_BASE=https://YOUR_HTTP_API.execute-api.us-east-1.amazonaws.com`
6. Upload the contents of `dashboard/` as the source bundle

## 8) GitHub Actions CI/CD

This repo includes `.github/workflows/deploy-eb.yml`.

### Secrets required in GitHub

Because most lab environments use **temporary** AWS credentials, GitHub deployment will only work while the credentials remain valid.

Create these repo secrets:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_REGION`
- `EB_APPLICATION_NAME`
- `EB_ENVIRONMENT_NAME`

## 9)  checklist

- Simulator sends data every few seconds
- Fog node validates + aggregates
- MQTT messages arrive in IoT Core
- IoT rule pushes to SQS
- Lambda updates both DynamoDB tables
- API returns latest + history JSON
- EB dashboard shows live cards + charts + history table
- GitHub Actions workflow shows successful deployment to EB

## 10) Sample DynamoDB design

### AquaLatest

- Partition key: `stationId` (String)

Stores the most recent processed payload per station.

### AquaHistory

- Partition key: `stationId` (String)
- Sort key: `ts` (String)

Stores all historical readings.

## 11) Notes for your report/demo

Use these points:

- **Fog node purpose**: early validation, range checks, aggregation, alert classification
- **Scalability**: IoT Core + SQS + Lambda decouple ingestion from processing
- **Fault tolerance**: SQS buffers burst traffic
- **Observability**: CloudWatch logs for fog, Lambda, and EB
- **Responsive UI**: dashboard cards + trend charts + history table

