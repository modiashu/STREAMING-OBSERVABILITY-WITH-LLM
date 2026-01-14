# Troubleshooting Learnings: Local Development Setup

**Date:** January 11, 2026  
**Context:** Setting up streaming observability platform in local development mode

---

## Overview

This document captures the issues encountered while setting up the complete data pipeline in local development mode (Python venv) and the solutions applied. The pipeline consists of:

```
Event Generator → Kafka → Spark Streaming → DuckDB → Anomaly Detector → Dashboard
```

---

## Issues and Solutions

### 1. Deprecated Python datetime.utcnow()

**Issue:**
```python
datetime.utcnow()  # Deprecated in Python 3.12
```

**Error:** DeprecationWarning for `datetime.utcnow()`

**Root Cause:**
- Python 3.12+ deprecated `utcnow()` in favor of timezone-aware datetimes
- The old method returns a "naive" datetime without timezone information

**Solution:**
```python
# Before
datetime.utcnow()

# After
from datetime import datetime, timezone
datetime.now(timezone.utc)
```

**Files Changed:**
- `event_generator/generator.py`

**Learning:** Always use timezone-aware datetimes for production systems. The new approach is more explicit and follows best practices.

---

### 2. Container vs Local Path Configurations

**Issue:**
```
OSError: [Errno 30] Read-only file system: '/data'
```

**Root Cause:**
- Default paths like `/data/observability.db` are absolute paths for container environments
- Local development doesn't have write access to `/data` directory
- Services were configured with container-specific defaults

**Solution:**
Change all default paths from absolute to relative:

```python
# Before
db_path = os.getenv('DUCKDB_PATH', '/data/observability.db')

# After
db_path = os.getenv('DUCKDB_PATH', './data/observability.db')
```

**Files Changed:**
- `scripts/init_db.py`
- `anomaly_detection/detector.py`
- `llm/narrator.py`
- `spark/streaming_job.py`

**Learning:** Always provide environment-appropriate defaults. Use relative paths for local development and let containers override with absolute paths via environment variables.

---

### 3. DuckDB Database Locking Issues

**Issue:**
```
IO Error: Could not set lock on file "observability.db": Resource temporarily unavailable
```

**Root Cause:**
- Multiple services trying to access DuckDB simultaneously with write locks
- DuckDB uses file-based locking and doesn't support concurrent writes well
- Read operations were opening write-mode connections unnecessarily

**Solution:**
Use read-only connections for query operations:

```python
# Before
def _get_connection(self):
    return duckdb.connect(self.db_path)

# After
def _get_connection(self, read_only: bool = False):
    return duckdb.connect(self.db_path, read_only=read_only)

# Usage
conn = self._get_connection(read_only=True)  # For queries
```

**Files Changed:**
- `anomaly_detection/detector.py`

**Additional Commands:**
```bash
# Check what's holding the lock
lsof ./data/observability.db

# Remove stale lock files
rm -f ./data/observability.db.wal ./data/observability.db.lock

# Kill stuck processes
pkill -f detector.py
```

**Learning:** 
- Use read-only connections whenever possible
- DuckDB is better for read-heavy workloads; consider alternatives for high-concurrency writes
- Always provide a way to check and clear locks during development

---

### 4. Spark Streaming - Empty Batches Problem

**Issue:**
Spark continuously processing empty batches despite event generator running:
```
Batch 0 is empty, skipping
Batch 1 is empty, skipping
...
```

**Root Cause:**
- Spark configured with `startingOffsets=latest` 
- Spark started AFTER event generator was already publishing
- Only reads new messages arriving after Spark starts
- Checkpoint files preserved old offset positions

**Diagnostic Steps:**
1. **Verify Kafka has messages:**
```python
from kafka import KafkaConsumer
consumer = KafkaConsumer('raw_events', bootstrap_servers='localhost:29092', auto_offset_reset='earliest')
for message in consumer:
    print(message.value)  # Should see events
    break
```

2. **Check Spark configuration:**
```python
.option("startingOffsets", "latest")  # Problem: misses existing messages
```

**Solution:**
```python
# Change to read from beginning
.option("startingOffsets", "earliest")

# AND delete checkpoint directory to force fresh start
rm -rf ./data/checkpoints
```

**Files Changed:**
- `spark/streaming_job.py`

**Learning:**
- Spark checkpoints override `startingOffsets` configuration
- For development: Use `earliest` and clean checkpoints frequently
- For production: Use `latest` to avoid reprocessing on restarts
- Always verify data exists in Kafka before debugging Spark

**Startup Order Matters:**
1. Start Kafka
2. Start Event Generator
3. Wait ~10 seconds
4. Start Spark (will read all accumulated messages)

---

### 5. Malformed Timestamp Format

**Issue:**
Spark batches empty despite Kafka having data and correct configuration.

**Root Cause:**
Event timestamps had BOTH timezone offset AND 'Z' suffix:
```
2026-01-11T23:09:52.214823+00:00Z  # WRONG: Double timezone marker
```

**Diagnostic Process:**
```python
# Python consumer could read, but Spark couldn't parse
consumer = KafkaConsumer(...)
for msg in consumer:
    print(msg.value)  # Showed malformed timestamp
```

**Problem Code:**
```python
# Creates "+00:00" then adds "Z"
datetime.now(timezone.utc).isoformat() + 'Z'
# Result: "2026-01-11T23:09:52.214823+00:00Z"
```

**Solution:**
```python
# Replace "+00:00" with "Z" 
datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
# Result: "2026-01-11T23:09:52.214823Z"
```

**Files Changed:**
- `event_generator/generator.py`

**Learning:**
- `datetime.now(timezone.utc).isoformat()` already includes timezone as `+00:00`
- Don't blindly append 'Z' without checking format
- Test timestamp parsing early in the pipeline
- Use consumer tests to verify message format before blaming downstream services

---

### 6. DuckDB SQL Syntax Error - Multiple Constraints

**Issue:**
```
Binder Error: Conflict target has to be provided for a DO UPDATE operation 
when the table has multiple UNIQUE/PRIMARY KEY constraints
```

**Root Cause:**
Table `service_metrics` has TWO constraints:
1. `PRIMARY KEY (id)`
2. `UNIQUE (window_start, service)`

DuckDB's `INSERT OR REPLACE` doesn't know which constraint to check for conflicts.

**Problem Code:**
```sql
INSERT OR REPLACE INTO service_metrics (...)  -- Ambiguous!
```

**Solution:**
Explicitly specify the conflict target:
```sql
INSERT INTO service_metrics (...)
VALUES (...)
ON CONFLICT (window_start, service) DO UPDATE SET
    request_count = EXCLUDED.request_count,
    error_count = EXCLUDED.error_count,
    ...
```

**Files Changed:**
- `spark/streaming_job.py`

**Learning:**
- `INSERT OR REPLACE` only works with single constraint
- Always specify `ON CONFLICT (columns)` when multiple constraints exist
- Use the UNIQUE constraint that represents the natural key (window + service)
- Test database writes early with sample data

---

### 7. Spark Checkpoint and Event Log Paths

**Issue:**
```
File file:/tmp/spark-events does not exist
```

**Root Cause:**
- Spark defaults to absolute system paths (`/tmp/spark-events`)
- Doesn't create directories automatically
- No control over checkpoint location in multi-user environments

**Solution:**
```python
# Create local directories
checkpoint_dir = os.getenv('SPARK_CHECKPOINT_DIR', './data/checkpoints')
event_log_dir = os.getenv('SPARK_EVENT_LOG_DIR', './data/spark-events')

os.makedirs(checkpoint_dir, exist_ok=True)
os.makedirs(event_log_dir, exist_ok=True)

spark = SparkSession.builder \
    .config("spark.sql.streaming.checkpointLocation", checkpoint_dir) \
    .config("spark.eventLog.enabled", "true") \
    .config("spark.eventLog.dir", f"file://{os.path.abspath(event_log_dir)}") \
    .getOrCreate()
```

**Files Changed:**
- `spark/streaming_job.py`

**Learning:**
- Always use project-relative paths for local development
- Create directories before Spark tries to use them
- Use absolute paths with `file://` protocol for Spark configs
- Make paths configurable via environment variables

---

### 8. Spark Streaming - Cannot Sort in Update Mode

**Issue:**
```
AnalysisException: Sorting is not supported on streaming DataFrames/Datasets, 
unless it is on aggregated DataFrame/Dataset in Complete output mode
```

**Root Cause:**
- Attempted to use `.orderBy()` on streaming DataFrame
- Sorting requires buffering all data, which breaks streaming semantics
- Only allowed in Complete output mode (not Update mode)

**Problem Code:**
```python
aggregated = events \
    .groupBy(...) \
    .agg(...) \
    .orderBy("window")  # ERROR in Update mode
```

**Solution:**
```python
# Remove orderBy - data arrives naturally ordered by event time
aggregated = events \
    .groupBy(...) \
    .agg(...)
# Let the consumer (database/detector) handle ordering if needed
```

**Files Changed:**
- `spark/streaming_job.py`

**Learning:**
- Streaming DataFrames process data incrementally
- Sorting breaks streaming model (requires seeing all data)
- If ordering matters downstream, do it in the sink/query
- Trust watermarks and windowing for temporal ordering

---

## Systematic Debugging Approach

### When Services Don't Communicate

1. **Verify each component independently:**
   ```bash
   # Is Kafka running?
   podman ps | grep kafka
   
   # Can I publish to Kafka?
   # (Test event generator standalone)
   
   # Can I consume from Kafka?
   python -c "from kafka import KafkaConsumer; ..."
   
   # Can I write to database?
   python -c "import duckdb; conn = duckdb.connect(...)"
   ```

2. **Check connection strings match:**
   - Event generator: `localhost:29092` (external Kafka port)
   - Spark: `localhost:29092` (same)
   - Container-to-container: `kafka:9092` (internal port)

3. **Inspect actual data:**
   ```python
   # Read raw messages
   consumer = KafkaConsumer('raw_events', ...)
   print(next(consumer).value)
   
   # Check database contents
   conn.execute('SELECT * FROM service_metrics LIMIT 5').fetchdf()
   ```

4. **Check file locks:**
   ```bash
   lsof ./data/observability.db
   rm -f ./data/*.lock ./data/*.wal
   ```

### When Spark Batches Are Empty

1. **Verify Kafka has data** (Python consumer test)
2. **Check startingOffsets configuration**
3. **Delete checkpoint directory**
4. **Verify timestamp format** (ISO 8601 compliance)
5. **Check Spark logs** for parsing errors

### When Database Writes Fail

1. **Check for lock conflicts** (`lsof`)
2. **Verify SQL syntax** (test in DuckDB CLI)
3. **Check constraint definitions** (`SHOW CREATE TABLE`)
4. **Use read-only connections** for queries

---

## Best Practices Learned

### Configuration Management

```python
# Always provide environment-appropriate defaults
db_path = os.getenv('DUCKDB_PATH', './data/observability.db')  # Local
# Container overrides: DUCKDB_PATH=/data/observability.db

# Make everything configurable
kafka_broker = os.getenv('KAFKA_BROKER', 'localhost:29092')
checkpoint_dir = os.getenv('SPARK_CHECKPOINT_DIR', './data/checkpoints')
```

### Database Access Patterns

```python
# Reads: Use read-only mode
conn = duckdb.connect(db_path, read_only=True)

# Writes: Use brief connections
try:
    conn = duckdb.connect(db_path)
    conn.execute(...)
    conn.commit()
finally:
    conn.close()  # Release lock ASAP
```

### Timestamp Handling

```python
# Always use timezone-aware datetimes
from datetime import datetime, timezone

# For UTC timestamps ending in 'Z'
timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
# Result: "2026-01-11T23:09:52.214823Z"
```

### Spark Streaming Development

```python
# Development mode
.option("startingOffsets", "earliest")  # Read all messages
# Clean checkpoints frequently: rm -rf ./data/checkpoints

# Production mode  
.option("startingOffsets", "latest")  # Only new messages
# Checkpoints persist across restarts
```

### Service Startup Order

```
1. Infrastructure (Kafka, Ollama)
2. Event Generator (populates Kafka)
3. Spark Streaming (aggregates to DB)
4. Anomaly Detector (reads from DB)
5. Dashboard (visualizes)
```

---

## Common Pitfalls

### ❌ Don't Do This

```python
# Absolute paths for local dev
db_path = '/data/observability.db'

# Opening write connections for reads
conn = duckdb.connect(db_path)  # Gets write lock!

# Naive datetime
datetime.utcnow()  # Deprecated

# Malformed timestamps
datetime.now(timezone.utc).isoformat() + 'Z'  # Double timezone!

# Ambiguous conflict resolution
INSERT OR REPLACE  # Which constraint?

# Sorting streaming data
streaming_df.orderBy('timestamp')  # Breaks streaming
```

### ✅ Do This Instead

```python
# Relative paths with env override
db_path = os.getenv('DUCKDB_PATH', './data/observability.db')

# Read-only for queries
conn = duckdb.connect(db_path, read_only=True)

# Timezone-aware datetime
datetime.now(timezone.utc)

# Clean timestamps
datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

# Explicit conflict target
ON CONFLICT (window_start, service) DO UPDATE

# Let streaming data flow naturally
streaming_df.groupBy(...).agg(...)  # No orderBy
```

---

## Tools and Commands Reference

### Debugging Commands

```bash
# Check running containers
podman ps | grep kafka

# Check file locks
lsof ./data/observability.db

# Kill stuck processes
pkill -f "detector.py"
pkill -f "spark-submit"

# Clean Spark checkpoints
rm -rf ./data/checkpoints

# Clean DuckDB locks
rm -f ./data/observability.db.wal ./data/observability.db.lock

# Test Kafka connectivity
python -c "from kafka import KafkaConsumer; consumer = KafkaConsumer('raw_events', bootstrap_servers='localhost:29092', auto_offset_reset='earliest'); print(next(consumer).value)"

# Query database
python -c "import duckdb; conn = duckdb.connect('./data/observability.db', read_only=True); print(conn.execute('SELECT COUNT(*) FROM service_metrics').fetchone())"
```

### Service Startup Commands

```bash
# Terminal T1 - Event Generator
source .venv/bin/activate
export KAFKA_BROKER=localhost:29092
python event_generator/generator.py

# Terminal T2 - Initialize DB (once)
source .venv/bin/activate
python scripts/init_db.py

# Terminal T3 - Spark Streaming
source .venv/bin/activate
export KAFKA_BROKER=localhost:29092
export DUCKDB_PATH=./data/observability.db
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 spark/streaming_job.py

# Terminal T4 - Anomaly Detector
source .venv/bin/activate
export DUCKDB_PATH=./data/observability.db
python anomaly_detection/detector.py

# Terminal T5 - Dashboard
source .venv/bin/activate
export DUCKDB_PATH=./data/observability.db
streamlit run dashboard/app.py
```

---

### 11. DuckDB Concurrent Write Locking

**Issue:**
```
duckdb.duckdb.IOException: IO Error: Could not set lock on file 
"./data/observability.db": Resource temporarily unavailable
```

**Error:** Multiple services (Spark, Detector, Narrator, Dashboard) trying to access DuckDB simultaneously resulted in lock conflicts and crashes.

**Root Cause:**
- **DuckDB is single-writer by design** - only one write connection allowed at a time
- Dashboard used `@st.cache_resource` decorator which kept a read-only connection **permanently open**
- Even read-only connections can block write locks in DuckDB
- Three writers (Spark, Detector, Narrator) competing for write access
- No retry logic meant first lock conflict caused immediate failure

**Solution 1: Add Retry Logic to All Writers**

All services that write to DuckDB need exponential backoff retry logic:

```python
def _get_connection(self, read_only: bool = False):
    """Get database connection with retry on lock errors"""
    max_retries = 5
    retry_delay = 0.5  # seconds
    
    for attempt in range(max_retries):
        try:
            return duckdb.connect(self.db_path, read_only=read_only)
        except Exception as e:
            if "Could not set lock" in str(e) and attempt < max_retries - 1:
                logger.debug(f"DB lock conflict, retrying in {retry_delay}s")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff: 0.5s → 1s → 2s → 4s
            else:
                raise
```

**Solution 2: Use Short-Lived Connections in Dashboard**

```python
# BEFORE (blocked writes indefinitely)
@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)

# AFTER (acquire, query, close immediately)
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)

# In main():
conn = get_connection()
metrics_df = fetch_metrics(conn, hours=time_window)
anomalies_df = fetch_anomalies(conn, hours=time_window)
summaries_df = fetch_incident_summaries(conn, hours=time_window)
conn.close()  # Release lock immediately
```

**Files Changed:**
- `anomaly_detection/detector.py` - Added retry logic to `_get_connection()`
- `spark/streaming_job.py` - Added retry logic in `write_to_duckdb()`
- `llm/narrator.py` - Added retry logic to `_get_connection()`
- `dashboard/app.py` - Removed `@st.cache_resource`, added `conn.close()`

**Learning:** 
- **DuckDB excels at analytics but has write concurrency limitations** - fine for development with retry logic, but consider alternatives for production (PostgreSQL, ClickHouse)
- **Cached database connections can cause subtle locking issues** - always close connections promptly
- **Retry logic with exponential backoff is essential** when multiple services access the same database
- **Test with all services running simultaneously** to catch concurrency issues

**Production Consideration:**
DuckDB may not be suitable for production with high write concurrency. Consider:
- PostgreSQL or TimescaleDB for time-series data
- ClickHouse for OLAP workloads
- Or architect with single writer pattern (e.g., all writes go through Spark only)

---

## Key Takeaways

1. **Test each pipeline stage independently** before connecting them
2. **Verify data format at boundaries** (Kafka messages, database records)
3. **Use appropriate connection modes** (read-only vs write)
4. **Match paths to environment** (container vs local)
5. **Handle Spark checkpoints properly** (clean for dev, preserve for prod)
6. **Follow startup order** (infrastructure → producers → processors → consumers)
7. **Make everything configurable** via environment variables
8. **Use timezone-aware datetimes** consistently
9. **Document debugging steps** for future reference
10. **Test error conditions** (missing data, locks, conflicts)
11. **Add retry logic for database locks** when using single-writer databases
12. **Use short-lived database connections** to minimize lock contention
13. **Test all services concurrently** to catch real-world race conditions

---

## Success Metrics

After applying all fixes, the complete pipeline works:

```
✅ Event Generator: Publishing 10 events/sec to Kafka
✅ Spark Streaming: Processing batches every 30 seconds
   - Batch 0: Wrote 12 records to DuckDB
   - search: requests=111, error_rate=0.90%, avg_latency=50.7ms
   - payments: requests=193, error_rate=2.59%, avg_latency=196.1ms
✅ Anomaly Detector: Running continuously with retry logic
✅ LLM Narrator: Generating incident summaries via Ollama
✅ Dashboard: Displaying metrics, anomalies, and LLM summaries
✅ Database: Lock conflicts resolved via retry logic and short-lived connections
✅ All services: Running stably in local development mode with concurrent access
```

---

## Files Modified

1. `event_generator/generator.py` - Fixed timestamp format, added timezone import
2. `scripts/init_db.py` - Changed default path from `/data` to `./data`
3. `anomaly_detection/detector.py` - Added read-only connections, fixed default path, added retry logic
4. `spark/streaming_job.py` - Fixed multiple issues:
   - Checkpoint and event log paths
   - Starting offsets configuration
   - SQL conflict resolution syntax
   - Removed orderBy from streaming
   - Added retry logic for DuckDB locks
5. `llm/narrator.py` - Added retry logic for database connections
6. `dashboard/app.py` - Fixed timezone queries, removed cached connections, added conn.close()
7. `DEVELOPMENT.md` - Added Spark streaming step to documentation

---

**Generated:** January 11, 2026  
**Status:** All issues resolved, pipeline operational
