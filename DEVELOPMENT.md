# Development Guide

This guide explains how to set up and work with the project in **development mode** using Python virtual environments.

## Development vs Production

### Production Setup (Container-Based)
- **Purpose**: Run the complete platform locally as it would run in production
- **Approach**: Everything runs in Podman containers
- **Use Case**: Testing end-to-end flow, demos, portfolio showcase
- **Command**: `make start`
- **Pros**: Complete isolation, production-like, easy to run
- **Cons**: Slower iteration, need to rebuild containers for changes

### Development Setup (venv-Based)
- **Purpose**: Develop and test individual services
- **Approach**: Local Python venv with UV package manager
- **Use Case**: Writing code, debugging, testing changes quickly
- **Command**: `make dev-setup`
- **Pros**: Fast iteration, easy debugging, no container rebuilds
- **Cons**: Requires local Kafka/Ollama for full testing

## Development Environment Setup

### Prerequisites

- **Python 3.11+**
- **UV Package Manager** (installed automatically by setup script)
- **Git**

Optional (for full local testing):
- **Kafka** (via container or local install)
- **Ollama** (for LLM testing)

### Quick Setup

```bash
# 1. Setup development environment
make dev-setup
# This installs UV, creates venv, and installs all dependencies

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Verify installation
python -c "import kafka, duckdb, streamlit; print('✓ All imports OK')"
```

### Manual Setup

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Create and activate venv
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"
```

## Development Workflow

### 1. Code Formatting

```bash
# Format all Python files
make dev-format

# Or manually:
black .
```

### 2. Linting

```bash
# Run linter
make dev-lint

# Or manually:
ruff check .
```

### 3. Type Checking

```bash
# Run mypy
mypy event_generator/ anomaly_detection/ llm/
```

### 4. Testing

```bash
# Run all tests
make dev-test

# Run specific test file
pytest tests/test_detector.py

# Run with coverage
pytest --cov=anomaly_detection tests/
```

## Running Services Locally

### Option 1: Individual Services (Development)

**Prerequisites**: Start supporting services first:

```bash
# Start only Kafka and Ollama
podman-compose up -d kafka ollama

# Download the LLM model (first time only, ~1.6GB)
podman-compose up -d ollama-init

# Wait for model download to complete
podman-compose logs -f ollama-init
```

**Then run services locally:**

```bash
# Terminal 1: Event Generator
source .venv/bin/activate
export KAFKA_BROKER=localhost:29092
python event_generator/generator.py

# Terminal 2: Initialize Database (run once)
source .venv/bin/activate
python scripts/init_db.py

# Terminal 3: Spark Streaming (aggregates events → metrics)
source .venv/bin/activate
export KAFKA_BROKER=localhost:29092
export DUCKDB_PATH=./data/observability.db

# For fresh start (clean checkpoints to read from beginning):
rm -rf ./data/checkpoints

# Start Spark streaming:
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 spark/streaming_job.py

# Terminal 4: Anomaly Detector
source .venv/bin/activate
export DUCKDB_PATH=./data/observability.db
python anomaly_detection/detector.py

# Terminal 5: LLM Narrator
source .venv/bin/activate
export DUCKDB_PATH=./data/observability.db
export OLLAMA_URL=http://localhost:11434
python llm/narrator.py

# Terminal 6: Dashboard
source .venv/bin/activate
export DUCKDB_PATH=./data/observability.db
streamlit run dashboard/app.py
```

### Option 2: Full Stack (Production)

```bash
# Run everything in containers
make start
```

## Project Structure for Development

```
.
├── .venv/                      # Python virtual environment (created by setup)
├── pyproject.toml              # Project dependencies (for UV)
├── requirements.txt            # Frozen dependencies (for containers)
│
├── event_generator/            # Editable: Event simulation
│   ├── generator.py
│   └── tests/                  # Add your tests here
│
├── anomaly_detection/          # Editable: Anomaly detection
│   ├── detector.py
│   └── tests/
│
├── llm/                        # Editable: LLM narrator
│   ├── narrator.py
│   └── tests/
│
├── dashboard/                  # Editable: Streamlit app
│   ├── app.py
│   └── tests/
│
├── spark/                      # Editable: Spark job
│   ├── streaming_job.py
│   └── tests/
│
└── scripts/                    # Development scripts
    ├── setup_dev.sh            # Development setup
    └── init_db.py              # Database initialization
```

## Common Development Tasks

### Adding a New Dependency

```bash
# Activate venv
source .venv/bin/activate

# Add dependency using UV (fast!)
uv pip install numpy

# Update pyproject.toml manually:
# Add "numpy>=1.24.0" to dependencies list

# Test the change
python -c "import numpy; print(numpy.__version__)"

# If working, update requirements.txt for containers:
pip freeze > requirements.txt
```

### Testing Database Changes

```bash
# Activate venv
source .venv/bin/activate

# Test schema changes
python scripts/init_db.py

# Query the database
python -c "
import duckdb
conn = duckdb.connect('./data/observability.db')
print(conn.execute('SHOW TABLES').fetchall())
conn.close()
"
```

### Testing Anomaly Detection Logic

```bash
# Activate venv
source .venv/bin/activate

# Run detector once
export DUCKDB_PATH=./data/observability.db
python -c "
from anomaly_detection.detector import AnomalyDetector
detector = AnomalyDetector('./data/observability.db')
detector.detect_anomalies()
"
```

## Troubleshooting Development Issues

### DuckDB Lock Errors

**Symptom:** `IO Error: Could not set lock on file`

**Cause:** DuckDB is single-writer. Multiple services trying to write simultaneously.

**Solution:** All services now have retry logic with exponential backoff. If you still see issues:
1. Ensure dashboard isn't holding connections (it should close them automatically)
2. Wait a few seconds between starting services
3. Check that old processes aren't hanging: `ps aux | grep python`

### Spark Not Processing Events

**Symptom:** "No recent metrics found" in detector logs

**Cause:** Spark checkpoint conflicts or database locks

**Solution:**
```bash
# Stop Spark
Ctrl+C in Spark terminal

# Clean checkpoints
rm -rf ./data/checkpoints

# Restart Spark
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 spark/streaming_job.py
```

### LLM Narrator Connection Refused

**Symptom:** `Connection refused` when calling Ollama

**Cause:** Corporate VPN/proxy blocking localhost connections

**Solution:**
```bash
# Disconnect VPN or set NO_PROXY
export NO_PROXY=localhost,127.0.0.1

# Then restart narrator
python llm/narrator.py
```

### Dashboard Shows Stale Data

**Symptom:** Dashboard not updating with new anomalies

**Cause:** Streamlit caching or auto-refresh disabled

**Solution:**
1. Check "Auto-refresh" toggle in sidebar is enabled
2. Manually refresh with `Ctrl+R` or `Cmd+R`
3. If still stuck, restart dashboard: `Ctrl+C` → `streamlit run dashboard/app.py`

### Services Keep Crashing

**Symptom:** Exit Code: 1 on all terminals

**Cause:** Multiple issues - check specific error messages

**Debugging Steps:**
```bash
# Check database is accessible
python -c "import duckdb; conn = duckdb.connect('./data/observability.db', read_only=True); print(conn.execute('SELECT COUNT(*) FROM service_metrics').fetchone()); conn.close()"

# Check Kafka is running
podman ps | grep kafka

# Check Kafka has messages
podman exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_events --from-beginning --max-messages 5

# Check for port conflicts
lsof -i :8501  # Dashboard
lsof -i :29092 # Kafka
lsof -i :11434 # Ollama
```

### Testing Dashboard Locally

```bash
# Activate venv
source .venv/bin/activate

# Set environment
export DUCKDB_PATH=./data/observability.db

# Run Streamlit
streamlit run dashboard/app.py

# Open: http://localhost:8501
```

### Debugging with IPython

```bash
# Activate venv
source .venv/bin/activate

# Start IPython
ipython

# Import and test your modules
>>> from anomaly_detection.detector import AnomalyDetector
>>> detector = AnomalyDetector('./data/observability.db')
>>> detector.detect_anomalies()
```

## Testing Strategy

### Unit Tests (Create these)

```bash
# Create test files in each module
mkdir -p tests/
touch tests/test_detector.py
touch tests/test_narrator.py
touch tests/test_generator.py
```

Example test structure:

```python
# tests/test_detector.py
import pytest
from anomaly_detection.detector import AnomalyDetector

def test_error_rate_detection():
    detector = AnomalyDetector(':memory:')
    # Add test logic
    assert True
```

### Integration Tests

```bash
# Test end-to-end flow locally
make dev-integration-test
```

## Performance Profiling

```bash
# Profile a service
python -m cProfile -o profile.stats anomaly_detection/detector.py

# View results
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

## Debugging Tips

### Enable Debug Logging

```python
# Add to any service
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Use Breakpoints

```python
# Add anywhere in code
import pdb; pdb.set_trace()

# Or use Python 3.7+ built-in
breakpoint()
```

### Check Database State

```bash
# Query metrics
python -c "
import duckdb
conn = duckdb.connect('./data/observability.db')
print(conn.execute('SELECT COUNT(*) FROM service_metrics').fetchone())
print(conn.execute('SELECT * FROM anomalies LIMIT 5').fetchdf())
"
```

## Switching Between Dev and Prod

### Development Mode
```bash
source .venv/bin/activate
export KAFKA_BROKER=localhost:29092
export DUCKDB_PATH=./data/observability.db
python event_generator/generator.py
```

### Production Mode
```bash
deactivate  # Exit venv if active
make start  # Start all containers
```

## CI/CD Integration (Future)

```yaml
# .github/workflows/test.yml (example)
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install UV
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Install dependencies
        run: uv pip install -e ".[dev]"
      - name: Run tests
        run: pytest
```

## Troubleshooting

### UV Installation Issues

```bash
# Manual install
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Verify
uv --version
```

### Import Errors

```bash
# Ensure venv is activated
source .venv/bin/activate

# Reinstall dependencies
uv pip install -e ".[dev]"
```

### Database Lock Issues

```bash
# If database is locked by container
make stop
rm ./data/observability.db
python scripts/init_db.py
```

### Ollama Model Download Issues (Corporate Proxy/VPN)

**Problem:** `ollama-init` fails with DNS errors like:
```
Error: dial tcp: lookup registry.ollama.ai: no such host
```

**Solution:**

1. **Configure proxy in `.env` file**:
   ```bash
   HTTP_PROXY=http://your-proxy.company.com:8080
   HTTPS_PROXY=http://your-proxy.company.com:8080
   NO_PROXY=localhost,127.0.0.1,kafka,ollama
   ```

2. **Restart containers**:
   ```bash
   podman-compose down
   podman-compose up -d kafka ollama
   podman-compose up -d ollama-init
   ```

3. **If still failing**: Try disconnecting VPN temporarily:
   ```bash
   # Disconnect corporate VPN
   podman rm -f ollama-init
   podman-compose up -d ollama-init
   podman logs -f ollama-init  # Watch for successful download
   ```

4. **Verify download**:
   ```bash
   curl http://localhost:11434/api/tags
   # Should show phi model in the list
   ```

## Best Practices

1. **Always activate venv** before running Python commands
2. **Use UV for dependency management** (it's much faster than pip)
3. **Test locally first** before rebuilding containers
4. **Keep pyproject.toml in sync** with requirements.txt
5. **Write tests** as you develop
6. **Use type hints** for better code quality
7. **Format code** before committing (black, ruff)

## Resources

- **UV Documentation**: https://github.com/astral-sh/uv
- **Pytest Documentation**: https://docs.pytest.org/
- **Black Formatter**: https://black.readthedocs.io/
- **Ruff Linter**: https://beta.ruff.rs/docs/

---

**Happy coding! 🚀**
