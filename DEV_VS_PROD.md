# Development vs Production Setup

This document clarifies the two ways to run this project: **Production Mode** (containers) and **Development Mode** (local venv).

## 🎯 Quick Decision Guide

**Choose Production Mode if you want to:**
- ✅ See the complete platform in action
- ✅ Demo the project to others
- ✅ Run it exactly as it would run in production
- ✅ Not worry about installing dependencies locally

**Choose Development Mode if you want to:**
- ✅ Modify and test code quickly
- ✅ Debug individual services
- ✅ Add new features or fix bugs
- ✅ Run only specific services you're working on

---

## 🐳 Production Mode (Container-Based)

### What It Is
All services run in **isolated Podman containers**, exactly as they would in a production deployment.

### Architecture
```
Your Machine
  ├── Podman Container: Kafka
  ├── Podman Container: Spark
  ├── Podman Container: Event Generator
  ├── Podman Container: Anomaly Detector
  ├── Podman Container: LLM Narrator
  ├── Podman Container: Airflow
  ├── Podman Container: Dashboard
  └── Podman Container: Ollama
```

### How to Use
```bash
# One command to rule them all
make init && make start

# Access dashboard
open http://localhost:8501
```

### Pros
- ✅ **Complete isolation** - No dependency conflicts
- ✅ **Production-like** - Runs exactly as it would in prod
- ✅ **Easy to share** - `docker-compose.yml` is self-contained
- ✅ **Clean system** - No local Python packages installed
- ✅ **Guaranteed to work** - Everything is pre-configured

### Cons
- ❌ **Slow iteration** - Need to rebuild containers for code changes
- ❌ **Resource intensive** - ~5GB RAM for all containers
- ❌ **Debugging harder** - Need to exec into containers
- ❌ **Build time** - Initial setup takes 2-3 minutes

### When to Use
- First time running the project
- Demonstrating to others
- Testing end-to-end flow
- Portfolio showcase
- When you need "it just works" behavior

---

## 💻 Development Mode (venv-Based)

### What It Is
Services run **locally on your machine** using a Python virtual environment managed by **UV** (ultra-fast package manager).

### Architecture
```
Your Machine
  ├── Python venv (.venv/)
  │   ├── All Python packages installed here
  │   ├── event_generator/generator.py (runs directly)
  │   ├── anomaly_detection/detector.py (runs directly)
  │   ├── llm/narrator.py (runs directly)
  │   └── dashboard/app.py (runs directly)
  │
  └── Podman Containers (only for infrastructure)
      ├── Kafka (still needed)
      └── Ollama (still needed)
```

### How to Use
```bash
# One-time setup
make dev-setup

# Activate environment
source .venv/bin/activate

# Run what you need
python event_generator/generator.py
python anomaly_detection/detector.py
streamlit run dashboard/app.py
```

### Pros
- ✅ **Fast iteration** - Edit code and run immediately
- ✅ **Easy debugging** - Use breakpoints, print statements
- ✅ **Low resource** - ~2GB RAM (only run what you need)
- ✅ **Familiar workflow** - Standard Python development
- ✅ **IDE integration** - Full code completion and linting

### Cons
- ❌ **Manual setup** - Need to start services individually
- ❌ **Dependencies** - Must manage Python environment
- ❌ **Partial testing** - Not testing containerization
- ❌ **Less isolated** - Could have dependency conflicts

### When to Use
- Developing new features
- Fixing bugs
- Testing individual services
- Debugging issues
- Rapid prototyping

---

## 📊 Side-by-Side Comparison

| Aspect | Production Mode 🐳 | Development Mode 💻 |
|--------|-------------------|-------------------|
| **Command** | `make start` | `make dev-setup` + `source .venv/bin/activate` |
| **Services** | All (12 containers) | Only what you run |
| **RAM Usage** | ~5GB | ~2GB |
| **Startup Time** | 2-3 minutes | <30 seconds |
| **Code Changes** | Rebuild container | Instant |
| **Debugging** | Container logs | Breakpoints, pdb |
| **Dependencies** | In containers | In .venv/ |
| **Isolation** | Complete | Process-level |
| **Use Case** | Production-like testing | Active development |

---

## 🔄 Common Workflows

### Scenario 1: First Time User
```bash
# Use production mode
make init
make start
make health
open http://localhost:8501
```

### Scenario 2: Adding a New Feature
```bash
# Use development mode
make dev-setup
source .venv/bin/activate

# Edit code
vim anomaly_detection/detector.py

# Test immediately
python anomaly_detection/detector.py

# Format and lint
make dev-format
make dev-lint
```

### Scenario 3: Testing End-to-End
```bash
# Use production mode
make restart  # Fresh start
make logs     # Monitor all services
```

### Scenario 4: Debugging Dashboard
```bash
# Use development mode
source .venv/bin/activate
export DUCKDB_PATH=./data/observability.db
streamlit run dashboard/app.py --server.runOnSave true
# Now edit dashboard/app.py - it auto-reloads!
```

---

## 🛠️ Hybrid Approach (Best of Both Worlds)

You can mix both approaches:

```bash
# Start infrastructure in containers
podman-compose up -d kafka ollama

# Run your service locally for development
source .venv/bin/activate
export KAFKA_BROKER=localhost:29092
python event_generator/generator.py  # Fast iteration here!

# Keep other services in containers
podman-compose up -d spark anomaly-detector
```

This gives you:
- ✅ Fast iteration on the service you're working on
- ✅ Full infrastructure support (Kafka, Ollama)
- ✅ Other services running as normal

---

## 📚 File Organization

### Production Files
```
docker-compose.yml        # Orchestrates all containers
*/Dockerfile             # Builds each service container
requirements.txt         # Frozen for container builds
```

### Development Files
```
pyproject.toml           # UV/pip-compatible dependencies
.venv/                   # Virtual environment (created by dev-setup)
scripts/setup_dev.sh     # Development environment setup
DEVELOPMENT.md           # Development guide
```

### Shared Files
```
event_generator/*.py     # Python code (same in both modes)
anomaly_detection/*.py
llm/*.py
dashboard/*.py
scripts/*.py
```

---

## ❓ FAQ

### Q: Which mode should I use?
**A:** Start with Production Mode to see it work, then switch to Development Mode when you want to change code.

### Q: Can I switch between modes?
**A:** Yes! They don't interfere with each other.

### Q: Do I need both?
**A:** No. Production Mode is sufficient for demos. Development Mode is optional for contributors.

### Q: Why UV instead of pip?
**A:** UV is 10-100x faster than pip for package installation. Perfect for development.

### Q: What if UV installation fails?
**A:** You can use pip instead:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Q: How do I clean up development environment?
**A:** `make dev-clean` removes `.venv/` and caches.

### Q: Can I use both simultaneously?
**A:** Yes, but they'll compete for ports (8501, 8080, etc.). Stop one before starting the other.

---

## 🚀 Production Deployment Considerations

Based on development learnings, here are key changes needed for true production deployment:

### 1. **Database: Replace DuckDB**

**Issue:** DuckDB is single-writer, causing lock contention with multiple services.

**Current State (Dev):**
- Using DuckDB with retry logic and short-lived connections
- Works for development but not scalable for production

**Production Options:**

**Option A: PostgreSQL with TimescaleDB**
```yaml
# Best for: Mature ecosystem, strong consistency, time-series optimization
database:
  type: postgresql
  host: timescaledb-cluster
  port: 5432
  connection_pool: 10-50 connections
  
Benefits:
  - Native concurrent writes
  - Proven production reliability
  - Excellent monitoring tools (pg_stat, pgbadger)
  - Time-series optimizations (continuous aggregates)
```

**Option B: ClickHouse**
```yaml
# Best for: Massive scale, analytical queries, high ingestion rates
database:
  type: clickhouse
  cluster: observability-cluster
  replicas: 3
  
Benefits:
  - Columnar storage for analytics
  - Scales to billions of rows
  - Sub-second query latency on aggregations
  - Native Kafka integration
```

**Option C: Single-Writer Architecture**
```
Keep DuckDB, but architect with single writer:
  Spark Streaming (only writer) → DuckDB
  All other services → Read-only queries
  
Benefits:
  - Minimal code changes
  - DuckDB's excellent analytical performance
  - Simpler deployment
```

### 2. **Path Configuration**

**Current (Dev):**
```python
# Hardcoded local paths
DB_PATH = './data/observability.db'
CHECKPOINT_PATH = './data/checkpoints'
```

**Production:**
```python
# Environment-driven, container-friendly paths
DB_PATH = os.getenv('DB_PATH', '/data/observability.db')
CHECKPOINT_PATH = os.getenv('CHECKPOINT_PATH', '/data/checkpoints')
LOG_PATH = os.getenv('LOG_PATH', '/var/log/observability')

# Use persistent volumes
volumes:
  - observability-data:/data
  - observability-checkpoints:/data/checkpoints
```

### 3. **Connection Management**

**Current (Dev):**
```python
# Direct connections with retry logic
conn = duckdb.connect(db_path, read_only=read_only)
```

**Production:**
```python
# Connection pooling for production databases
from psycopg2.pool import ThreadedConnectionPool

pool = ThreadedConnectionPool(
    minconn=5,
    maxconn=20,
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)

def get_connection():
    return pool.getconn()

def release_connection(conn):
    pool.putconn(conn)
```

### 4. **Error Handling & Monitoring**

**Add for Production:**

```python
# Structured logging with correlation IDs
import structlog
logger = structlog.get_logger()

# Metrics export (Prometheus)
from prometheus_client import Counter, Histogram, Gauge

anomalies_detected = Counter('anomalies_detected_total', 'Anomalies', ['service', 'severity'])
db_query_duration = Histogram('db_query_duration_seconds', 'DB Query Time')
active_connections = Gauge('db_connections_active', 'Active DB Connections')

# Distributed tracing (OpenTelemetry)
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("detect_anomalies"):
    # detection logic
```

### 5. **Resource Limits & Scaling**

**Add to Kubernetes/Docker Compose:**

```yaml
services:
  spark-streaming:
    resources:
      limits:
        cpus: '4'
        memory: 8G
      reservations:
        cpus: '2'
        memory: 4G
    deploy:
      replicas: 1  # Spark handles parallelism internally
      
  anomaly-detector:
    resources:
      limits:
        cpus: '2'
        memory: 2G
    deploy:
      replicas: 3  # Can scale horizontally
      
  llm-narrator:
    resources:
      limits:
        cpus: '4'
        memory: 8G  # LLM needs more resources
    deploy:
      replicas: 2
```

### 6. **Secrets Management**

**Current (Dev):**
```bash
# Plain text environment variables
export DUCKDB_PATH=./data/observability.db
```

**Production:**
```yaml
# Use Kubernetes Secrets or HashiCorp Vault
apiVersion: v1
kind: Secret
metadata:
  name: observability-db
type: Opaque
data:
  db-password: <base64-encoded>
  db-host: <base64-encoded>
  
# Mount as environment variables
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: observability-db
        key: db-password
```

### 7. **Health Checks & Readiness Probes**

**Add to all services:**

```python
# health_check.py
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/health')
def health():
    try:
        # Check database connection
        conn = get_connection()
        conn.execute('SELECT 1')
        conn.close()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503

@app.route('/ready')
def ready():
    # Check if service is ready to accept traffic
    # (Kafka connected, model loaded, etc.)
    return jsonify({"status": "ready"}), 200
```

```yaml
# In docker-compose or Kubernetes
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 8. **Spark Checkpointing**

**Current (Dev):**
```bash
# Delete checkpoints for clean restarts
rm -rf ./data/checkpoints
```

**Production:**
```yaml
# Preserve checkpoints for exactly-once processing
volumes:
  - spark-checkpoints:/data/checkpoints  # Persistent volume

# Never delete in production!
# Checkpoints enable:
#   - Exactly-once semantics
#   - Recovery from failures
#   - Offset management
```

### 9. **Observability for the Observability Platform**

**Add to Production:**

```yaml
# Monitor the monitors!
monitoring:
  - Prometheus + Grafana for metrics
  - ELK Stack for centralized logging
  - Jaeger for distributed tracing
  - PagerDuty for alerting
  
alerts:
  - Service down > 2 minutes
  - Database connection pool exhausted
  - Kafka consumer lag > 1000 messages
  - Anomaly detector stopped detecting
  - LLM response time > 30 seconds
```

---

## 📋 Production Readiness Checklist

### Database
- [ ] Replace DuckDB with production database (PostgreSQL/ClickHouse)
- [ ] Configure connection pooling
- [ ] Set up automated backups
- [ ] Configure replication/high availability

### Configuration
- [ ] All paths use environment variables
- [ ] Secrets stored in secret management system
- [ ] Configuration externalized (ConfigMaps/env files)

### Resilience
- [ ] Retry logic with exponential backoff (✅ Already done)
- [ ] Circuit breakers for external services
- [ ] Health checks on all services
- [ ] Graceful shutdown handlers

### Scaling
- [ ] Resource limits defined
- [ ] Horizontal scaling tested (detector, narrator)
- [ ] Load testing completed
- [ ] Auto-scaling rules defined

### Monitoring
- [ ] Prometheus metrics exported
- [ ] Structured logging implemented
- [ ] Distributed tracing enabled
- [ ] Alerting rules configured
- [ ] Dashboards created (Grafana)

### Security
- [ ] Secrets encrypted at rest and in transit
- [ ] Network policies defined
- [ ] Service accounts with least privilege
- [ ] Security scanning in CI/CD

### Operations
- [ ] CI/CD pipeline configured
- [ ] Rollback procedure documented
- [ ] Runbooks created for common issues
- [ ] On-call rotation established

---

## 🎯 Summary

**Both modes use the same Python code** - the only difference is how services are run (containers vs local Python).

**Development Mode:**
- DuckDB with retry logic ✅
- Local file paths
- Manual service management
- Quick iteration

**Production Mode (Current):**
- DuckDB in containers ⚠️ (Works but not scalable)
- Container paths
- docker-compose orchestration
- Suitable for demos/POC

**Production Mode (Recommended):**
- PostgreSQL/ClickHouse 🚀
- Persistent volumes
- Kubernetes orchestration
- Full observability stack
- High availability
- Auto-scaling

---

For detailed instructions:
- **Production**: See [QUICKSTART.md](QUICKSTART.md)
- **Development**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Troubleshooting**: See [TROUBLESHOOTING_LEARNINGS.md](TROUBLESHOOTING_LEARNINGS.md)

