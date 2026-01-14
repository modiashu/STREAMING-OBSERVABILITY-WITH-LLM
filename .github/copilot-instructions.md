# AI Coding Agent Instructions

## Project Overview

This is a **streaming observability platform** showcasing real-time telemetry processing, anomaly detection, and LLM-based incident explanation. The system processes simulated service events through a complete data pipeline: Event Generator → Kafka → Spark Streaming → DuckDB → Anomaly Detector → LLM Narrator → Dashboard.

**Critical constraint:** 100% local execution using Podman containers (production) or Python venv (development).

## Architecture & Data Flow

### Component Boundaries
- **Event Generator** ([event_generator/generator.py](event_generator/generator.py)): Simulates 10 events/sec for 3 services (checkout, payments, search), injects anomalies probabilistically (5% default)
- **Kafka**: 3 topics (`raw_events`, `aggregated_metrics`, `anomalies`), container listens on port 29092 for local dev
- **Spark Streaming** ([spark/streaming_job.py](spark/streaming_job.py)): 1-minute tumbling windows, computes p50/p95/p99 latencies + error rates, writes to DuckDB
- **DuckDB** ([data/observability.db](data/observability.db)): Embedded analytics DB with 3 tables (service_metrics, anomalies, incident_summaries), uses file-based locking
- **Anomaly Detector** ([anomaly_detection/detector.py](anomaly_detection/detector.py)): Rule-based (error_rate > 3x baseline OR latency > 2x SLA), runs every 60s
- **LLM Narrator** ([llm/narrator.py](llm/narrator.py)): Local Ollama (Phi model) generates summaries from aggregated data only (never raw events)
- **Dashboard** ([dashboard/app.py](dashboard/app.py)): Streamlit UI with 10s auto-refresh, displays metrics + anomalies + LLM summaries

### Critical Integration Points
- All Python services use **environment variables** for paths/URLs (e.g., `KAFKA_BROKER`, `DUCKDB_PATH`, `OLLAMA_URL`)
- DuckDB connections MUST use `read_only=True` for queries to avoid lock conflicts (see [TROUBLESHOOTING_LEARNINGS.md](TROUBLESHOOTING_LEARNINGS.md))
- Spark requires `--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0` for Kafka integration
- VPN/proxy issues: Export `NO_PROXY=localhost,127.0.0.1` for Ollama connectivity

## Development Workflows

### Dual-Mode Operation
The project supports **two distinct modes** (see [DEV_VS_PROD.md](DEV_VS_PROD.md)):

1. **Production Mode** (containers): `make init && make start` - runs complete system in Podman
2. **Development Mode** (venv): `make dev-setup && source .venv/bin/activate` - runs services locally with UV package manager

### Key Commands
```bash
# Development setup (one-time)
make dev-setup                          # Creates venv, installs deps with UV

# Run individual services (in separate terminals)
python event_generator/generator.py     # Requires: export KAFKA_BROKER=localhost:29092
python anomaly_detection/detector.py    # Requires: export DUCKDB_PATH=./data/observability.db
streamlit run dashboard/app.py          # Starts dashboard on :8501

# Spark requires spark-submit
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 spark/streaming_job.py

# Fresh start (clears Spark state)
rm -rf ./data/checkpoints && make dev-clean-checkpoints

# Database inspection
python scripts/init_db.py               # Initialize schema
python -c "import duckdb; conn = duckdb.connect('./data/observability.db', read_only=True); print(conn.execute('SELECT * FROM service_metrics LIMIT 5').fetchdf())"
```

### Testing & Debugging
- **No automated tests yet** - verify via dashboard or direct DB queries
- **Logs**: Each service logs to stdout with standard format `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Common issues**: See [TROUBLESHOOTING_LEARNINGS.md](TROUBLESHOOTING_LEARNINGS.md) for DuckDB locks, Spark checkpointing, VPN/Ollama connectivity

## Project-Specific Conventions

### Path Handling Pattern
**Always use relative paths in code defaults** to support both container and local execution:
```python
# ✅ Correct (development-friendly)
db_path = os.getenv('DUCKDB_PATH', './data/observability.db')

# ❌ Wrong (container-only)
db_path = os.getenv('DUCKDB_PATH', '/data/observability.db')
```
Containers override via environment variables in [docker-compose.yml](docker-compose.yml).

### DuckDB Concurrency Pattern
**Critical:** Use read-only connections for query operations to prevent locking:
```python
def _get_connection(self, read_only: bool = False):
    max_retries, retry_delay = 5, 0.5
    for attempt in range(max_retries):
        try:
            return duckdb.connect(self.db_path, read_only=read_only)
        except Exception as e:
            if "Could not set lock" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise
```
See [anomaly_detection/detector.py#L38](anomaly_detection/detector.py) for reference implementation.

### Timestamp Pattern
**Always use timezone-aware datetimes** (Python 3.12+ best practice):
```python
# ✅ Correct
from datetime import datetime, timezone
datetime.now(timezone.utc)

# ❌ Deprecated
datetime.utcnow()
```

### Anomaly Injection Pattern
Event generator uses stateful anomaly injection (2-5 minute duration windows) for realistic testing. Toggle via `anomaly_probability` constructor param.

## File Organization

- **No `src/` directory**: Services are top-level folders (event_generator/, spark/, etc.)
- **Scripts in scripts/**: Database init, health checks, dev utilities
- **Data in data/**: Generated at runtime (DB file, checkpoints, spark-events) - excluded from git
- **Documentation**: Comprehensive guides (README, DESIGN, DEVELOPMENT, QUICKSTART, TROUBLESHOOTING_LEARNINGS)
- **Makefile**: Primary interface for all workflows (production + development targets)

## When Making Changes

1. **Adding new services**: Follow existing pattern (Dockerfile + requirements + main script), update [docker-compose.yml](docker-compose.yml) and [Makefile](Makefile)
2. **Database schema changes**: Update [scripts/init_db.py](scripts/init_db.py), test with `make dev-clean-data && python scripts/init_db.py`
3. **Spark job changes**: Clear checkpoints (`rm -rf ./data/checkpoints`) to avoid state conflicts
4. **Environment variables**: Document in [.env.example](.env.example) and README
5. **Always test both modes**: Production (`make start`) and development (`make dev-*`) workflows

## Common Gotchas

- **Spark not processing events?** Clear checkpoints: `rm -rf ./data/checkpoints`
- **DuckDB lock errors?** Stagger service starts by 10s, or ensure read-only connections for queries
- **Ollama connection refused?** Check `NO_PROXY` environment variable for VPN/proxy bypass
- **Services can't find Kafka?** Local dev uses `localhost:29092`, containers use `kafka:9092`
- **Missing dependencies?** Run `make dev-setup` (uses UV for fast installs), not `pip install`
