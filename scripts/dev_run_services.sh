#!/bin/bash

# Development Services Quick Start Script
# Provides commands to run each service in development mode

set -e

cat << 'EOF'
=====================================
Development Mode - Service Commands
=====================================

Prerequisites:
  1. Run: make dev-setup
  2. Run: podman-compose up -d kafka ollama
  3. Run: python scripts/init_db.py

Then open 6 terminals and run:

TERMINAL 1 - Event Generator:
  source .venv/bin/activate
  export KAFKA_BROKER=localhost:29092
  python event_generator/generator.py

TERMINAL 2 - Spark Streaming:
  source .venv/bin/activate
  export KAFKA_BROKER=localhost:29092
  export DUCKDB_PATH=./data/observability.db
  rm -rf ./data/checkpoints  # For fresh start
  spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 spark/streaming_job.py

TERMINAL 3 - Anomaly Detector:
  source .venv/bin/activate
  export DUCKDB_PATH=./data/observability.db
  python anomaly_detection/detector.py

TERMINAL 4 - LLM Narrator:
  source .venv/bin/activate
  export DUCKDB_PATH=./data/observability.db
  export OLLAMA_URL=http://localhost:11434
  # If VPN blocks localhost: export NO_PROXY=localhost,127.0.0.1
  python llm/narrator.py

TERMINAL 5 - Dashboard:
  source .venv/bin/activate
  export DUCKDB_PATH=./data/observability.db
  streamlit run dashboard/app.py

TERMINAL 6 - Monitor (Optional):
  # Check database contents:
  source .venv/bin/activate
  python -c "
import duckdb
from datetime import datetime
conn = duckdb.connect('./data/observability.db', read_only=True)

print('=== Service Metrics (last 5) ===')
print(conn.execute('SELECT window_start, service, request_count, error_rate FROM service_metrics ORDER BY window_start DESC LIMIT 5').fetchdf())

print('\n=== Anomalies (last 5) ===')
print(conn.execute('SELECT detected_at, service, anomaly_type, severity FROM anomalies ORDER BY detected_at DESC LIMIT 5').fetchdf())

print(f'\n=== Current Time: {datetime.now()} ===')
conn.close()
"

Access Dashboard:
  http://localhost:8501

Quick Status Check:
  make dev-status

Troubleshooting:
  - DuckDB lock errors: Wait 10s between service starts
  - Spark not processing: rm -rf ./data/checkpoints
  - LLM connection refused: export NO_PROXY=localhost,127.0.0.1
  - See TROUBLESHOOTING_LEARNINGS.md for details

=====================================
EOF

echo ""
read -p "Press Enter to continue..."
