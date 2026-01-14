# Streaming Observability Platform

A production-style, local streaming observability platform that demonstrates real-time telemetry processing, anomaly detection, and LLM-based incident explanation generation.

## 🎯 Overview

This project showcases senior data engineering skills through a complete, working observability pipeline that:
- Ingests and processes service telemetry in near-real-time
- Performs windowed aggregations using Spark Structured Streaming
- Detects anomalies using rule-based algorithms
- Generates human-readable incident explanations using a local LLM
- Orchestrates workflows with Apache Airflow
- Visualizes metrics and incidents in an interactive dashboard

**Key Constraints:**
- ✅ 100% local execution (no cloud services)
- ✅ Runs entirely via Podman Compose
- ✅ Uses local LLM only (Ollama with Phi model)
- ✅ Production-reasonable architecture and code quality

## 🏗️ Architecture

```
┌─────────────────┐
│ Event Generator │ (Python - simulates service telemetry)
│  - checkout     │
│  - payments     │
│  - search       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              Kafka (3 topics)                       │
│  - raw_events                                       │
│  - aggregated_metrics                               │
│  - anomalies                                        │
└──────────┬──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│      Spark Structured Streaming                      │
│  - 1-minute tumbling windows                         │
│  - Aggregations per service:                         │
│    • request_count, error_rate                       │
│    • avg_latency, p50, p95, p99                      │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│              DuckDB (Metrics Store)                  │
│  Tables:                                             │
│  - service_metrics                                   │
│  - anomalies                                         │
│  - incident_summaries                                │
└──────┬────────────────┬──────────────────────────────┘
       │                │
       ▼                ▼
┌─────────────────┐  ┌──────────────────────────┐
│ Anomaly Detector│  │   LLM Narrator           │
│  (Rule-based)   │  │  (Ollama - Phi model)    │
│  - Error surge  │  │  - Reads aggregated data │
│  - Latency spike│  │  - Generates summaries   │
└─────────────────┘  └──────────────────────────┘
       │                │
       └────────┬───────┘
                │
                ▼
┌──────────────────────────────────────────────────────┐
│            Apache Airflow (Orchestration)            │
│  DAGs:                                               │
│  - monitoring_dag: Health checks every 5 min         │
│  - data_quality_dag: Validation & cleanup every 6h   │
└──────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────┐
│         Streamlit Dashboard                          │
│  - Real-time metrics visualization                   │
│  - Anomaly timeline                                  │
│  - LLM-generated incident summaries                  │
└──────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
.
├── docker-compose.yml          # Podman Compose configuration
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── .gitignore
├── README.md
│
├── data/                      # Database and checkpoints (generated)
│   ├── observability.db       # DuckDB database
│   └── checkpoints/           # Spark checkpoints
│
├── event_generator/           # Telemetry event simulator
│   ├── generator.py           # Event generation logic
│   └── Dockerfile
│
├── spark/                     # Spark Structured Streaming
│   └── streaming_job.py       # Main streaming job
│
├── anomaly_detection/         # Anomaly detection service
│   ├── detector.py            # Rule-based detector
│   └── Dockerfile
│
├── llm/                       # LLM narrator service
│   ├── narrator.py            # Incident explanation generator
│   └── Dockerfile
│
├── airflow/                   # Airflow orchestration
│   ├── dags/
│   │   ├── monitoring_dag.py  # Health monitoring
│   │   └── data_quality_dag.py # Data validation
│   ├── Dockerfile
│   └── requirements-airflow.txt
│
├── dashboard/                 # Streamlit dashboard
│   ├── app.py                 # Main dashboard app
│   └── Dockerfile
│
└── scripts/                   # Utility scripts
    ├── init.sh                # Initialization script
    ├── init_db.py             # Database schema setup
    ├── health_check.sh        # Service health check
    └── shutdown.sh            # Cleanup script
```

## 🚀 Quick Start

**Choose your setup mode:**

### 🐳 Production Mode (Recommended for First Run)

Run the complete platform in containers - perfect for demos and portfolio showcase.

**Prerequisites:**
- **Podman** and **Podman Compose** installed
- **8GB+ RAM** (recommended)
- **10GB+ disk space**

**Setup:**

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd streaming-observability-with-llm
   ```

2. **Initialize and start:**
   ```bash
   make init    # Create directories and database
   make start   # Start all services
   ```

3. **Check status** (~2-3 minutes for initialization):
   ```bash
   make health
   ```

4. **Access the platform:**
   - **Dashboard:** http://localhost:8501
   - **Airflow:** http://localhost:8080 (admin/admin)

See [QUICKSTART.md](QUICKSTART.md) for detailed production setup.

---

### 💻 Development Mode (For Code Changes)

Run services locally with Python venv - perfect for development and testing.

**Prerequisites:**
- **Python 3.11+**
- **UV package manager** (installed automatically)

**Setup:**

1. **Setup development environment:**
   ```bash
   make dev-setup
   ```
   This installs UV, creates a virtual environment, and installs all dependencies (fast!).

2. **Activate the environment:**
   ```bash
   source .venv/bin/activate
   ```

3. **Run individual services:**
   ```bash
   # Start supporting services (Kafka, Ollama)
   podman-compose up -d kafka ollama
   

   # Download the LLM model (first time only, ~1.6GB)
   podman-compose up -d ollama-init
   
   # Wait for model download to complete
   podman-compose logs -f ollama-init
   
   # Run services locally
   python event_generator/generator.py
   python anomaly_detection/detector.py
   streamlit run dashboard/app.py
   ```

See [DEVELOPMENT.md](DEVELOPMENT.md) for complete development workflow.

---

### 📊 Key Differences

| Feature | Production Mode 🐳 | Development Mode 💻 |
|---------|-------------------|-------------------|
| **Setup** | `make start` | `make dev-setup` |
| **Isolation** | Containers | Python venv |
| **Use Case** | Complete platform | Individual services |
| **Iteration Speed** | Slower (rebuild containers) | Fast (direct code changes) |
| **Resource Usage** | ~5GB RAM | ~2GB RAM |
| **Best For** | Demos, portfolio | Development, debugging |

---

## 🎮 Usage

### Viewing the Dashboard

Navigate to http://localhost:8501 to see:
- **Real-time metrics** (request rate, error rate, latency)
- **Anomaly timeline** (color-coded by severity)
- **LLM-generated incident summaries**

The dashboard auto-refreshes every 30 seconds.

### Monitoring with Airflow

Access Airflow at http://localhost:8080:
- **monitoring_dag**: Runs every 5 minutes to check pipeline health
- **data_quality_dag**: Runs every 6 hours for data validation and cleanup

### Checking Service Health

```bash
./scripts/health_check.sh
```

This shows:
- Service status (Kafka, Ollama, Airflow, Dashboard)
- Database record counts

### Viewing Logs

```bash
# All services
podman-compose logs -f

# Specific service
podman-compose logs -f event-generator
podman-compose logs -f spark-streaming
podman-compose logs -f anomaly-detector
podman-compose logs -f llm-narrator
```

### Stopping the Platform

```bash
podman-compose down
```

Or use the provided script:
```bash
./scripts/shutdown.sh
```

Data persists in `./data/` directory.

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and modify as needed:

```bash
# Kafka
KAFKA_BROKER=kafka:9092
KAFKA_RAW_EVENTS_TOPIC=raw_events

# DuckDB
DUCKDB_PATH=/data/observability.db

# LLM
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=phi

# Event Generation
ANOMALY_PROBABILITY=0.05  # 5% chance of anomaly injection
EVENTS_PER_SECOND=10
```

### Anomaly Detection Thresholds

Thresholds are defined in `anomaly_detection/detector.py`:

```python
ERROR_RATE_MULTIPLIER = 3.0  # Alert if 3x baseline
LATENCY_THRESHOLDS = {
    'checkout': 300,   # 300ms SLA
    'payments': 400,
    'search': 150
}
```

## 📊 Data Flow

1. **Event Generation**: Simulates 10 events/second across 3 services
2. **Kafka Ingestion**: Events published to `raw_events` topic
3. **Spark Processing**: 
   - 1-minute tumbling windows
   - Aggregations computed per service
   - Results written to DuckDB
4. **Anomaly Detection**:
   - Runs every 60 seconds
   - Compares metrics against baselines
   - Records anomalies to database
5. **LLM Narration**:
   - Detects unprocessed anomalies
   - Builds context from aggregated metrics
   - Calls local Ollama API for explanation
   - Stores summaries in database
6. **Visualization**: Dashboard queries DuckDB and renders charts

## 🧪 Testing Anomalies

The event generator automatically injects anomalies with configurable probability (default 5%). To manually trigger more anomalies:

1. Increase anomaly probability:
   ```bash
   # Edit docker-compose.yml
   # Change: ANOMALY_PROBABILITY: 0.05 to 0.20
   podman-compose restart event-generator
   ```

2. Watch for anomalies:
   ```bash
   podman-compose logs -f anomaly-detector
   podman-compose logs -f llm-narrator
   ```

3. View in dashboard at http://localhost:8501

## 🏆 Design Decisions & Trade-offs

### Why These Technologies?

- **Kafka**: Industry standard for event streaming, handles backpressure well
- **Spark Structured Streaming**: Production-grade streaming engine with excellent windowing support
- **DuckDB**: Embedded analytical database, perfect for local execution, fast aggregations
- **Airflow**: De facto standard for workflow orchestration
- **Ollama + Phi**: Local LLM that runs on laptops, responsible AI usage (small model, minimal calls)
- **Streamlit**: Rapid dashboard development, Python-native

### Key Trade-offs

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| Rule-based anomaly detection | Less sophisticated than ML | Simple, explainable, no training data needed |
| 1-minute windows | Not sub-second precision | Balances latency vs. computational load |
| DuckDB vs. PostgreSQL | Single-node only | Simpler setup, faster for analytics |
| Local LLM (Phi) | Less capable than GPT-4 | Privacy, cost, local execution |
| Ollama API calls | Slight latency | More flexible than embedding models |

### Production Considerations

If deploying to production:
- Replace DuckDB with distributed store (ClickHouse, TimescaleDB)
- Add Kafka cluster with replication
- Implement ML-based anomaly detection
- Use larger LLM or cloud API (with rate limiting)
- Add authentication and RBAC
- Implement alerting (PagerDuty, Slack)
- Add distributed tracing (Jaeger)

## 📈 Metrics & Observability

The platform generates the following metrics per service:

- **Request Count**: Total requests in window
- **Error Count**: HTTP 4xx/5xx responses
- **Error Rate**: Percentage of failed requests
- **Avg Latency**: Mean response time (ms)
- **P50/P95/P99 Latency**: Percentile latencies

Anomalies detected:
- **Error Surge**: Error rate > 3x baseline
- **Latency Spike**: Avg latency > 2x SLA threshold

## 🧹 Maintenance

### Data Retention

The `data_quality_dag` automatically cleans up:
- Metrics older than 7 days
- Resolved anomalies older than 7 days
- Incident summaries older than 7 days

### Manual Cleanup

```bash
# Remove database
rm ./data/observability.db

# Remove checkpoints
rm -rf ./data/checkpoints/*

# Remove logs
rm -rf ./data/logs/*
```

### Resetting the Platform

```bash
podman-compose down
rm -rf ./data/*
./scripts/init.sh
podman-compose up -d
```

## 🐛 Troubleshooting

### Services Not Starting

```bash
# Check service status
podman-compose ps

# View logs
podman-compose logs <service-name>
```

### No Metrics in Dashboard

1. Check Kafka is receiving events:
   ```bash
   podman-compose logs event-generator
   ```

2. Check Spark is processing:
   ```bash
   podman-compose logs spark-streaming
   ```

3. Verify database has data:
   ```bash
   python3 scripts/health_check.sh
   ```

### LLM Not Generating Summaries

1. Check Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. Verify model is pulled:
   ```bash
   podman-compose logs ollama-init
   ```

3. Check narrator logs:
   ```bash
   podman-compose logs llm-narrator
   ```

### Ollama Model Download Fails (Corporate Proxy/VPN)

**Symptoms:**
- `ollama-init` logs show: `dial tcp: lookup registry.ollama.ai: no such host`
- Ollama container is "unhealthy"
- Model download fails repeatedly

**Solutions:**

1. **Configure proxy settings** in `.env`:
   ```bash
   HTTP_PROXY=http://your-proxy.company.com:8080
   HTTPS_PROXY=http://your-proxy.company.com:8080
   NO_PROXY=localhost,127.0.0.1,kafka,ollama,zookeeper
   ```

2. **Update docker-compose.yml** with proxy settings for ollama-init service (see docker-compose.yml lines 93-101)

3. **If on corporate VPN**: Try disconnecting VPN temporarily for model download:
   ```bash
   # Disconnect VPN
   podman rm -f ollama-init
   podman-compose up -d ollama-init
   podman logs -f ollama-init  # Watch download progress
   # Reconnect VPN after download completes
   ```

4. **Restart containers** after updating settings:
   ```bash
   podman-compose down
   podman-compose up -d kafka ollama
   podman-compose up -d ollama-init
   ```

### High Memory Usage

- Reduce Spark parallelism in `docker-compose.yml`:
  ```yaml
  --executor-memory 512m
  --driver-memory 512m
  ```

- Reduce event generation rate:
  ```yaml
  EVENTS_PER_SECOND: 5
  ```

## 🤝 Contributing

This is a portfolio project, but suggestions are welcome! Please open an issue for discussion.

## 📜 License

MIT License - See LICENSE file for details

## 👤 Author

**Your Name**
- LinkedIn: [https://www.linkedin.com/in/modi-ashutosh/]
- GitHub: [https://github.com/modiashu]

## 🙏 Acknowledgments

- Apache Spark, Kafka, and Airflow communities
- Ollama for local LLM hosting
- Streamlit for rapid dashboard development

---
