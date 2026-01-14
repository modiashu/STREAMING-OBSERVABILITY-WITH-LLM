# Quick Start Guide

Get the Streaming Observability Platform running in 5 minutes.

## Prerequisites Check

```bash
# Check Podman
podman --version
# Should see: podman version 4.x or higher

# Check Podman Compose
podman-compose --version
# Should see: podman-compose version 1.x or higher

# Check Python
python3 --version
# Should see: Python 3.11 or higher

# Check available memory
free -h
# Should have at least 8GB RAM available
```

## Installation Steps

### 1. Clone and Setup

```bash
# Clone repository
git clone <your-repo-url>
cd streaming-observability-with-llm

# Initialize platform
make init
# Or manually: ./scripts/init.sh
```

**Expected output:**
```
Creating data directory...
Creating .env file from template...
Initializing DuckDB database...
Setup completed successfully!
```

### 2. Start Services

```bash
make start
# Or manually: podman-compose up -d
```

**Expected output:**
```
Starting all services...
[+] Running 14/14
 ✔ Container zookeeper              Started
 ✔ Container kafka                  Started
 ✔ Container ollama                 Started
 ✔ Container kafka-init             Started
 ✔ Container event-generator        Started
 ✔ Container spark-streaming        Started
 ✔ Container anomaly-detector       Started
 ✔ Container llm-narrator           Started
 ✔ Container airflow-postgres       Started
 ✔ Container airflow-webserver      Started
 ✔ Container airflow-scheduler      Started
 ✔ Container dashboard              Started
```

### 3. Wait for Initialization (2-3 minutes)

```bash
# Check service health
make health
```

**Expected output:**
```
Kafka: ✓ Running
Ollama: ✓ Running
Airflow: ✓ Running
Dashboard: ✓ Running
Database: ✓ Exists
  - Metrics: 0 (initial)
  - Anomalies: 0 (initial)
  - Summaries: 0 (initial)
```

### 4. Access the Dashboard

Open your browser to: **http://localhost:8501**

You should see:
- Request rate charts (will populate within 1-2 minutes)
- Error rate charts
- Latency charts
- Anomaly timeline (will show anomalies as they occur)

## What You Should See

### After 2 minutes:

**Dashboard Overview:**
- Total Requests: ~1,200 (10 events/sec × 120 sec)
- Avg Error Rate: ~2-5%
- Anomalies Detected: 0-1
- Active Anomalies: 0-1

**Service Metrics Tab:**
- Line charts showing traffic for checkout, payments, search
- All three services should have similar patterns

### After 5 minutes:

**Anomalies Section:**
- Check for any detected anomalies (orange/red markers)
- Click on anomaly timeline to see details

**Incident Summaries:**
- If anomalies were detected, LLM summaries should appear
- Expand to see explanation and possible causes

## Verification Checklist

- [ ] Dashboard loads successfully
- [ ] Metrics charts show data
- [ ] All 3 services (checkout, payments, search) have data
- [ ] Request counts are increasing
- [ ] Airflow accessible at http://localhost:8080
- [ ] Both DAGs visible in Airflow

## Common Issues

### "No metrics data available"

**Solution:**
```bash
# Check if Spark is running
podman-compose logs spark-streaming

# Look for "Streaming query started"
# If not found, restart Spark:
podman-compose restart spark-streaming
```

### Dashboard shows "Failed to connect to database"

**Solution:**
```bash
# Check if database exists
ls -lh ./data/observability.db

# If missing, reinitialize:
python3 scripts/init_db.py

# Restart dashboard:
podman-compose restart dashboard
```

### Services won't start

**Solution:**
```bash
# Check logs
podman-compose logs

# Common issue: Port conflicts
# Check if ports are available:
netstat -tuln | grep -E '8501|8080|9092|11434'

# If ports are taken, stop conflicting services
```

### High CPU usage

**Solution:**
```bash
# Reduce event generation rate
# Edit docker-compose.yml:
# EVENTS_PER_SECOND: 5 (instead of 10)

# Restart event generator:
podman-compose restart event-generator
```

## Next Steps

### Explore the Platform

1. **Watch for Anomalies**
   - Wait 5-10 minutes
   - Check anomaly timeline in dashboard
   - Read LLM-generated summaries

2. **View Airflow DAGs**
   - Go to http://localhost:8080
   - Login: admin / admin
   - Click on "monitoring_dag"
   - Check execution history

3. **Query the Database**
   ```bash
   python3
   >>> import duckdb
   >>> conn = duckdb.connect('./data/observability.db')
   >>> conn.execute("SELECT service, AVG(error_rate) FROM service_metrics GROUP BY service").df()
   ```

4. **Check Logs**
   ```bash
   # View all logs
   make logs

   # View specific service
   make logs-anomaly
   make logs-llm
   ```

### Experiment

1. **Increase Anomaly Rate**
   ```bash
   # Edit docker-compose.yml
   # Change: ANOMALY_PROBABILITY: 0.20
   podman-compose restart event-generator
   ```

2. **Adjust Detection Thresholds**
   ```bash
   # Edit anomaly_detection/detector.py
   # Change ERROR_RATE_MULTIPLIER or LATENCY_THRESHOLDS
   podman-compose restart anomaly-detector
   ```

3. **Try Different LLM Models**
   ```bash
   # Edit docker-compose.yml
   # Change: OLLAMA_MODEL: qwen (instead of phi)
   podman-compose restart ollama-init llm-narrator
   ```

## Stopping the Platform

```bash
# Stop all services
make stop

# Or manually:
podman-compose down
```

Data persists in `./data/` directory.

## Getting Help

If you encounter issues:

1. Check logs: `make logs`
2. Run health check: `make health`
3. Review troubleshooting section in README.md
4. Open an issue on GitHub

## Success Criteria

You've successfully set up the platform if:

✅ Dashboard shows metrics for all 3 services
✅ Metrics are updating in real-time
✅ At least one anomaly has been detected
✅ LLM has generated an incident summary
✅ Airflow DAGs are running successfully

**Congratulations! Your streaming observability platform is running.**

## Clean Up

To remove everything:

```bash
make clean
```

This will:
- Stop all containers
- Remove all data
- Free up disk space

You can always reinitialize with `make init` and `make start`.
