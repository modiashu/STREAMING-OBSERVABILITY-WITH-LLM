"""
DuckDB Schema Initialization
Creates tables for metrics, anomalies, and incident summaries
"""

import duckdb
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database(db_path: str):
    """
    Initialize DuckDB database with required tables
    
    Args:
        db_path: Path to DuckDB database file
    """
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Initializing database at: {db_path}")
    
    conn = duckdb.connect(db_path)
    
    try:
        # Table 1: Service Metrics (1-minute aggregations)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_metrics (
                id INTEGER PRIMARY KEY,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                service VARCHAR NOT NULL,
                request_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                error_rate DOUBLE NOT NULL,
                avg_latency_ms DOUBLE NOT NULL,
                p50_latency_ms DOUBLE,
                p95_latency_ms DOUBLE,
                p99_latency_ms DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(window_start, service)
            )
        """)
        logger.info("Created table: service_metrics")
        
        # Table 2: Anomalies
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                service VARCHAR NOT NULL,
                anomaly_type VARCHAR NOT NULL,
                severity VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                metric_value DOUBLE NOT NULL,
                baseline_value DOUBLE,
                threshold_value DOUBLE,
                description TEXT,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at TIMESTAMP
            )
        """)
        logger.info("Created table: anomalies")
        
        # Table 3: Incident Summaries (LLM-generated explanations)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_summaries (
                id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                anomaly_id INTEGER NOT NULL,
                service VARCHAR NOT NULL,
                time_window_start TIMESTAMP NOT NULL,
                time_window_end TIMESTAMP NOT NULL,
                summary TEXT NOT NULL,
                possible_causes TEXT,
                affected_metrics TEXT,
                llm_model VARCHAR,
                FOREIGN KEY (anomaly_id) REFERENCES anomalies(id)
            )
        """)
        logger.info("Created table: incident_summaries")
        
        # Create indexes for better query performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_window 
            ON service_metrics(window_start, window_end)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_service 
            ON service_metrics(service)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_service 
            ON anomalies(service)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_detected 
            ON anomalies(detected_at)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_resolved 
            ON anomalies(resolved)
        """)
        
        logger.info("Created indexes")
        
        # Create sequences for auto-increment IDs
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_service_metrics_id START 1
        """)
        
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_anomalies_id START 1
        """)
        
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_incident_summaries_id START 1
        """)
        
        logger.info("Created sequences")
        
        # Verify tables
        tables = conn.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'main'
        """).fetchall()
        
        logger.info(f"Tables in database: {[t[0] for t in tables]}")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

def main():
    """Main entry point"""

    db_path = os.getenv('DUCKDB_PATH', './data/observability.db')
    init_database(db_path)

if __name__ == '__main__':
    main()
