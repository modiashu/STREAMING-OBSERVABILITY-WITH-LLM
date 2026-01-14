"""
Spark Structured Streaming Job
Reads events from Kafka, performs windowed aggregations, and writes to DuckDB
"""

import os
import sys
import logging
import time
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, count, avg, sum as spark_sum,
    when, expr, percentile_approx, current_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, TimestampType
)
import duckdb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Event schema
EVENT_SCHEMA = StructType([
    StructField("event_time", StringType(), False),
    StructField("service", StringType(), False),
    StructField("endpoint", StringType(), False),
    StructField("latency_ms", IntegerType(), False),
    StructField("status_code", IntegerType(), False)
])

def init_spark_session(app_name: str = "ObservabilityStreaming") -> SparkSession:
    """Initialize Spark session with Kafka support"""

    logger.info("Initializing Spark session...")
    
    checkpoint_dir = os.getenv('SPARK_CHECKPOINT_DIR', './data/checkpoints')
    event_log_dir = os.getenv('SPARK_EVENT_LOG_DIR', './data/spark-events')
    
    # Create directories if they don't exist
    os.makedirs(checkpoint_dir, exist_ok=True)
    os.makedirs(event_log_dir, exist_ok=True)
    
    spark = SparkSession.builder \
        .appName(app_name) \
        .config("spark.sql.streaming.checkpointLocation", checkpoint_dir) \
        .config("spark.sql.shuffle.partitions", "2") \
        .config("spark.sql.streaming.schemaInference", "true") \
        .config("spark.eventLog.enabled", "true") \
        .config("spark.eventLog.dir", f"file://{os.path.abspath(event_log_dir)}") \
        .config("spark.history.fs.logDirectory", f"file://{os.path.abspath(event_log_dir)}") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info(f"Spark version: {spark.version}")
    return spark

def write_to_duckdb(batch_df, batch_id):
    """
    Write batch of aggregated metrics to DuckDB
    
    Args:
        batch_df: DataFrame with aggregated metrics
        batch_id: Batch identifier
    """
    logger.info(f"Processing batch {batch_id}")
    
    if batch_df.isEmpty():
        logger.info(f"Batch {batch_id} is empty, skipping")
        return
    
    # Convert to Pandas for DuckDB insertion
    pandas_df = batch_df.toPandas()
    
    # Prepare data for insertion
    pandas_df['window_start'] = pandas_df['window'].apply(lambda x: x['start'])
    pandas_df['window_end'] = pandas_df['window'].apply(lambda x: x['end'])
    pandas_df = pandas_df.drop('window', axis=1)
    
    # Rename columns to match DB schema
    pandas_df = pandas_df.rename(columns={
        'total_requests': 'request_count',
        'total_errors': 'error_count'
    })
    

    db_path = os.getenv('DUCKDB_PATH', './data/observability.db')
    

    # Retry logic for DuckDB lock conflicts
    max_retries = 5
    retry_delay = 0.5
    conn = None
    
    for attempt in range(max_retries):
        try:
            conn = duckdb.connect(db_path)
            break
        except Exception as e:
            if "Could not set lock" in str(e) and attempt < max_retries - 1:
                logger.debug(f"DB lock conflict, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise
    
    if conn is None:
        raise Exception("Failed to acquire database connection after retries")
    
    try:
        

        # Insert with conflict resolution (update if exists)
        for _, row in pandas_df.iterrows():
            conn.execute("""
                INSERT INTO service_metrics (
                    id, window_start, window_end, service, 
                    request_count, error_count, error_rate, avg_latency_ms,
                    p50_latency_ms, p95_latency_ms, p99_latency_ms
                ) VALUES (
                    nextval('seq_service_metrics_id'),
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT (window_start, service) DO UPDATE SET
                    request_count = EXCLUDED.request_count,
                    error_count = EXCLUDED.error_count,
                    error_rate = EXCLUDED.error_rate,
                    avg_latency_ms = EXCLUDED.avg_latency_ms,
                    p50_latency_ms = EXCLUDED.p50_latency_ms,
                    p95_latency_ms = EXCLUDED.p95_latency_ms,
                    p99_latency_ms = EXCLUDED.p99_latency_ms
            """, [
                row['window_start'],
                row['window_end'],
                row['service'],
                int(row['request_count']),
                int(row['error_count']),
                float(row['error_rate']),
                float(row['avg_latency_ms']),
                float(row['p50_latency_ms']) if row['p50_latency_ms'] else None,
                float(row['p95_latency_ms']) if row['p95_latency_ms'] else None,
                float(row['p99_latency_ms']) if row['p99_latency_ms'] else None
            ])
        
        conn.commit()
        logger.info(f"Batch {batch_id}: Wrote {len(pandas_df)} records to DuckDB")
        
        # Log sample data
        for _, row in pandas_df.head(3).iterrows():
            logger.info(
                f"  {row['service']}: requests={row['request_count']}, "
                f"error_rate={row['error_rate']:.2%}, "
                f"avg_latency={row['avg_latency_ms']:.1f}ms"
            )
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error writing batch {batch_id} to DuckDB: {e}")
        raise

def run_streaming_job(spark: SparkSession):
    """Run the main streaming job"""
    kafka_broker = os.getenv('KAFKA_BROKER', 'kafka:9092')
    topic = os.getenv('KAFKA_RAW_EVENTS_TOPIC', 'raw_events')
    
    logger.info(f"Starting streaming from Kafka: {kafka_broker}, topic: {topic}")
    

    # Read from Kafka
    raw_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_broker) \
        .option("subscribe", topic) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    logger.info("Connected to Kafka stream")
    
    # Parse JSON events
    events = raw_stream.select(
        from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data")
    ).select("data.*")
    
    # Convert event_time string to timestamp
    events = events.withColumn(
        "event_time", 
        col("event_time").cast(TimestampType())
    )
    
    # Add error indicator
    events = events.withColumn(
        "is_error",
        when(col("status_code") >= 400, 1).otherwise(0)
    )
    
    # Perform windowed aggregations (1-minute tumbling window)

    aggregated = events \
        .withWatermark("event_time", "2 minutes") \
        .groupBy(
            window(col("event_time"), "1 minute"),
            col("service")
        ) \
        .agg(
            count("*").alias("total_requests"),
            spark_sum("is_error").alias("total_errors"),
            avg("latency_ms").alias("avg_latency_ms"),
            percentile_approx("latency_ms", 0.5).alias("p50_latency_ms"),
            percentile_approx("latency_ms", 0.95).alias("p95_latency_ms"),
            percentile_approx("latency_ms", 0.99).alias("p99_latency_ms")
        ) \
        .withColumn(
            "error_rate",
            col("total_errors") / col("total_requests")
        )
    
    # Write to DuckDB using foreachBatch
    query = aggregated.writeStream \
        .outputMode("update") \
        .foreachBatch(write_to_duckdb) \
        .trigger(processingTime='30 seconds') \
        .start()
    
    logger.info("Streaming query started")
    
    # Wait for termination
    query.awaitTermination()

def main():
    """Main entry point"""

    logger.info("=== Spark Structured Streaming Job Starting ===")
    
    # Initialize database first
    db_path = os.getenv('DUCKDB_PATH', './data/observability.db')
    logger.info(f"Ensuring database exists at: {db_path}")
    
    # Database should already be initialized by init_db.py
    # Just verify it exists
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}. Run 'python scripts/init_db.py' first.")
        sys.exit(1)
    
    # Wait for Kafka to be ready
    logger.info("Waiting for Kafka to be ready...")
    import time
    time.sleep(15)
    
    # Initialize Spark and run streaming job
    spark = init_spark_session()
    
    try:
        run_streaming_job(spark)
    except KeyboardInterrupt:
        logger.info("Streaming job interrupted by user")
    except Exception as e:
        logger.error(f"Streaming job failed: {e}")
        raise
    finally:
        spark.stop()
        logger.info("Spark session stopped")

if __name__ == '__main__':
    main()
