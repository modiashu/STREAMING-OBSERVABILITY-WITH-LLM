# System Design Document

## Executive Summary

The Streaming Observability Platform is a production-style data engineering project that demonstrates end-to-end telemetry processing, anomaly detection, and automated incident analysis using modern streaming technologies.

## System Requirements

### Functional Requirements

1. **Event Ingestion**: Continuously ingest service telemetry events (10+ events/second)
2. **Real-time Aggregation**: Compute windowed metrics within 1 minute of event occurrence
3. **Anomaly Detection**: Detect error rate and latency anomalies within 1 minute of occurrence
4. **Incident Explanation**: Generate human-readable explanations for detected anomalies
5. **Visualization**: Display metrics, anomalies, and summaries in real-time dashboard
6. **Orchestration**: Monitor pipeline health and perform maintenance tasks

### Non-Functional Requirements

1. **Scalability**: Handle 10-100 events/second on a single machine
2. **Reliability**: Survive container restarts without data loss
3. **Latency**: End-to-end latency < 2 minutes (event to dashboard)
4. **Resource Efficiency**: Run on laptop with 8GB RAM
5. **Maintainability**: Clean, documented, production-style code

## Architecture Decisions

### 1. Streaming Engine: Apache Spark

**Decision**: Use Spark Structured Streaming for event processing

**Alternatives Considered**:
- Flink: More complex setup, overkill for single-node
- Kafka Streams: Limited window operations, less flexible
- Python stream processing: Not production-grade

**Rationale**:
- Industry-standard streaming engine
- Excellent windowing and aggregation support
- Handles late data and watermarking
- Easy to test and debug locally

### 2. Message Queue: Apache Kafka

**Decision**: Use Kafka for event buffering

**Alternatives Considered**:
- RabbitMQ: Less suited for streaming workloads
- Redis Streams: Less mature ecosystem
- Direct DB writes: No backpressure handling

**Rationale**:
- Decouples event generation from processing
- Provides replay capability
- Production-standard technology
- Handles backpressure naturally

### 3. Storage: DuckDB

**Decision**: Use DuckDB for metrics storage

**Alternatives Considered**:
- PostgreSQL: Overkill for single-node, slower for analytics
- SQLite: Poor concurrent write performance
- Parquet files: Harder to query interactively

**Rationale**:
- Embedded, no separate server needed
- Excellent analytical query performance
- SQL interface familiar to data engineers
- Perfect for local execution

### 4. Anomaly Detection: Rule-based

**Decision**: Use statistical thresholds for anomaly detection

**Alternatives Considered**:
- ML models (LSTM, Isolation Forest): Require training data, complex
- Statistical models (ARIMA): Overkill for demo
- External services: Violates local-only constraint

**Rationale**:
- Simple, explainable, debuggable
- No training data required
- Production-reasonable baseline
- Easy to tune and extend

### 5. LLM Integration: Local Ollama

**Decision**: Use Ollama with Phi model for incident explanation

**Alternatives Considered**:
- Cloud APIs (OpenAI, Claude): Violates local-only constraint
- Larger local models: Too resource-intensive
- No LLM: Missing key differentiator

**Rationale**:
- Runs locally on laptop
- Small model footprint
- Responsible AI usage (aggregated data only)
- Demonstrates modern tech integration

## Data Models

### Event Schema

```python
{
    "event_time": "2024-01-09T12:34:56Z",
    "service": "checkout",
    "endpoint": "/api/cart",
    "latency_ms": 150,
    "status_code": 200
}
```

### Metrics Schema

```sql
CREATE TABLE service_metrics (
    id INTEGER PRIMARY KEY,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    service VARCHAR,
    request_count INTEGER,
    error_count INTEGER,
    error_rate DOUBLE,
    avg_latency_ms DOUBLE,
    p50_latency_ms DOUBLE,
    p95_latency_ms DOUBLE,
    p99_latency_ms DOUBLE
)
```

### Anomaly Schema

```sql
CREATE TABLE anomalies (
    id INTEGER PRIMARY KEY,
    detected_at TIMESTAMP,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    service VARCHAR,
    anomaly_type VARCHAR,
    severity VARCHAR,
    metric_name VARCHAR,
    metric_value DOUBLE,
    baseline_value DOUBLE,
    threshold_value DOUBLE,
    description TEXT,
    resolved BOOLEAN
)
```

## Processing Pipeline

### Stage 1: Event Generation

```
Event Generator
  ↓
  Simulates 3 services: checkout, payments, search
  Injects anomalies probabilistically (5% default)
  Publishes to Kafka raw_events topic
  Rate: 10 events/second
```

### Stage 2: Stream Processing

```
Kafka Consumer (Spark)
  ↓
  Read from raw_events topic
  Parse JSON events
  Apply 1-minute tumbling window
  Compute aggregations per service:
    - count(*) as request_count
    - sum(is_error) as error_count
    - avg(latency_ms)
    - percentile_approx(latency_ms, [0.5, 0.95, 0.99])
  Write to DuckDB
  Checkpoint state for fault tolerance
```

### Stage 3: Anomaly Detection

```
Anomaly Detector (Every 60s)
  ↓
  Query recent metrics from DuckDB
  Calculate baselines (1-hour rolling average)
  Compare current metrics to baselines:
    - Error rate > 3x baseline → Error Surge
    - Latency > 2x SLA threshold → Latency Spike
  Record anomalies to database
```

### Stage 4: LLM Narration

```
LLM Narrator (Every 60s)
  ↓
  Query unprocessed anomalies
  Fetch related metrics for context
  Build prompt with:
    - Time window
    - Service name
    - Metric deltas (current vs baseline)
    - Anomaly description
  Call Ollama API (Phi model)
  Parse response into structured format
  Store incident summary
```

### Stage 5: Visualization

```
Streamlit Dashboard (Real-time)
  ↓
  Query DuckDB for:
    - Recent metrics (time-series)
    - Anomalies (timeline)
    - Incident summaries
  Render interactive charts
  Auto-refresh every 30 seconds
```

## Monitoring & Orchestration

### Airflow DAGs

**monitoring_dag** (every 5 minutes):
1. Check Kafka consumer lag
2. Verify metrics freshness (< 5 min old)
3. Confirm anomaly detection is running
4. Generate health report

**data_quality_dag** (every 6 hours):
1. Validate metrics data (null checks, outliers)
2. Clean up old data (> 7 days)
3. Optimize database (ANALYZE tables)

## Performance Characteristics

### Throughput

- Event generation: 10 events/sec = 600 events/min
- Spark processing: 1-minute batches = ~600 records/batch
- Anomaly detection: 3 services × 5 metrics = 15 checks/minute
- LLM calls: Max 5 anomalies/minute (rate-limited)

### Latency

```
Event → Kafka:           < 10ms
Kafka → Spark:           < 5s (micro-batch interval)
Spark → DuckDB:          < 1s (write latency)
Anomaly Detection:       < 60s (check interval)
LLM Narration:          < 60s (check interval)
Total E2E Latency:      < 2 minutes
```

### Resource Usage

```
Component          Memory    CPU
────────────────────────────────
Kafka              512MB     5%
Spark              1GB       15%
Ollama             2GB       20%
Airflow            512MB     5%
Dashboard          256MB     2%
Other services     512MB     3%
────────────────────────────────
Total              ~5GB      50%
```

## Failure Modes & Recovery

### Kafka Failure

**Symptom**: Events not being ingested
**Detection**: Monitoring DAG, event-generator logs
**Recovery**: Restart Kafka container, replay from last offset

### Spark Failure

**Symptom**: Metrics not updating
**Detection**: Metrics freshness check in monitoring DAG
**Recovery**: Restart Spark container, resume from checkpoint

### Database Corruption

**Symptom**: Query errors, missing data
**Detection**: Data quality DAG validation errors
**Recovery**: Stop all services, restore from backup or reinitialize

### LLM Service Failure

**Symptom**: No new incident summaries
**Detection**: Check llm-narrator logs
**Recovery**: Restart Ollama and narrator containers

## Security Considerations

### Current State (Local Demo)

- No authentication on services
- No encryption at rest or in transit
- No access control on database
- No input validation on LLM prompts

### Production Recommendations

1. **Authentication**: Add Kafka ACLs, Airflow RBAC, dashboard auth
2. **Encryption**: TLS for Kafka, encrypt DuckDB at rest
3. **Input Validation**: Sanitize event data, limit LLM prompt size
4. **Network Isolation**: Use Docker networks, firewall rules
5. **Secrets Management**: Use Vault or similar for credentials

## Testing Strategy

### Unit Tests (Not Implemented - Future Work)

- Event generator: Validate event schema, anomaly injection
- Anomaly detector: Test threshold calculations
- LLM narrator: Mock Ollama API, test prompt building

### Integration Tests (Not Implemented - Future Work)

- End-to-end flow: Event → Dashboard
- Fault injection: Kill services, verify recovery
- Data quality: Validate aggregation correctness

### Manual Testing

1. Start platform: `make start`
2. Wait 2-3 minutes for data flow
3. Check dashboard: Verify metrics appear
4. Wait for anomaly: Check anomaly timeline
5. Verify LLM summary: Check incident summaries section

## Future Enhancements

### Phase 2 (ML-Based Detection)

- Implement time-series forecasting (Prophet, LSTM)
- Train models on historical data
- Compare ML vs rule-based accuracy

### Phase 3 (Distributed Deployment)

- Replace DuckDB with ClickHouse/TimescaleDB
- Deploy Spark on cluster (YARN or K8s)
- Add Kafka replication

### Phase 4 (Advanced Features)

- Correlation analysis across services
- Root cause analysis (dependency graphs)
- Alerting integration (Slack, PagerDuty)
- Distributed tracing (Jaeger integration)

## References

- Apache Spark Structured Streaming: https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html
- Kafka Documentation: https://kafka.apache.org/documentation/
- DuckDB: https://duckdb.org/docs/
- Ollama: https://ollama.ai/
- Apache Airflow: https://airflow.apache.org/docs/
