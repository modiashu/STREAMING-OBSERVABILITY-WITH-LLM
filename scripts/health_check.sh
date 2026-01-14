#!/bin/bash

# Health check script to verify all services are running

echo "Checking service health..."
echo ""

# Check Kafka
echo -n "Kafka: "
if curl -s http://localhost:29092 > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "✗ Not responding"
fi

# Check Ollama
echo -n "Ollama: "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "✗ Not responding"
fi

# Check Airflow
echo -n "Airflow: "
if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "✗ Not responding"
fi

# Check Dashboard
echo -n "Dashboard: "
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo "✓ Running"
else
    echo "✗ Not responding"
fi

echo ""

# Check database
if [ -f ./data/observability.db ]; then
    echo "Database: ✓ Exists"
    
    # Show record counts
    python3 << EOF
import duckdb
conn = duckdb.connect('./data/observability.db')
metrics = conn.execute("SELECT COUNT(*) FROM service_metrics").fetchone()[0]
anomalies = conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
summaries = conn.execute("SELECT COUNT(*) FROM incident_summaries").fetchone()[0]
print(f"  - Metrics: {metrics}")
print(f"  - Anomalies: {anomalies}")
print(f"  - Summaries: {summaries}")
conn.close()
EOF
else
    echo "Database: ✗ Not found"
fi
