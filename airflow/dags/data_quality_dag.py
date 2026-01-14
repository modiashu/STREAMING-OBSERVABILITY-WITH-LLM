"""
Data Quality DAG
Validates data quality and performs cleanup operations
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logging.warning("DuckDB not installed - DAG will run in dummy mode")

logger = logging.getLogger(__name__)

def validate_metrics_data(**context):
    """Validate metrics data quality"""
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB not available - skipping validation")
        return True
    
    db_path = '/data/observability.db'
    
    try:
        conn = duckdb.connect(db_path)
        
        # Check for null values
        null_check = conn.execute("""
            SELECT COUNT(*) as count
            FROM service_metrics
            WHERE service IS NULL 
            OR request_count IS NULL 
            OR error_rate IS NULL
            OR window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """).fetchone()[0]
        
        if null_check > 0:
            logger.warning(f"Found {null_check} records with null values")
        
        # Check for negative values
        negative_check = conn.execute("""
            SELECT COUNT(*) as count
            FROM service_metrics
            WHERE request_count < 0 
            OR error_count < 0
            OR avg_latency_ms < 0
            OR window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """).fetchone()[0]
        
        if negative_check > 0:
            logger.error(f"Found {negative_check} records with negative values!")
        
        # Check for outliers
        outlier_check = conn.execute("""
            SELECT COUNT(*) as count
            FROM service_metrics
            WHERE avg_latency_ms > 30000  -- More than 30 seconds seems wrong
            OR error_rate > 1.0  -- Error rate > 100%
            OR window_start >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """).fetchone()[0]
        
        if outlier_check > 0:
            logger.warning(f"Found {outlier_check} potential outlier records")
        
        logger.info("Data quality validation completed")
        
        return {
            'null_count': null_check,
            'negative_count': negative_check,
            'outlier_count': outlier_check
        }
        
    except Exception as e:
        logger.error(f"Error validating metrics data: {e}")
        raise
    finally:
        conn.close()

def cleanup_old_data(**context):
    """Clean up old data to manage database size"""
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB not available - skipping cleanup")
        return True
    
    db_path = '/data/observability.db'
    retention_days = 7  # Keep 7 days of data
    
    try:
        conn = duckdb.connect(db_path)
        
        # Delete old metrics
        deleted_metrics = conn.execute(f"""
            DELETE FROM service_metrics
            WHERE window_start < CURRENT_TIMESTAMP - INTERVAL '{retention_days} days'
        """).fetchone()
        
        # Delete old resolved anomalies
        deleted_anomalies = conn.execute(f"""
            DELETE FROM anomalies
            WHERE resolved = TRUE
            AND resolved_at < CURRENT_TIMESTAMP - INTERVAL '{retention_days} days'
        """).fetchone()
        
        # Delete old incident summaries
        deleted_summaries = conn.execute(f"""
            DELETE FROM incident_summaries
            WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '{retention_days} days'
        """).fetchone()
        
        conn.commit()
        
        logger.info(f"Cleanup completed - Retention: {retention_days} days")
        logger.info(f"  Deleted old metrics")
        logger.info(f"  Deleted old anomalies")
        logger.info(f"  Deleted old incident summaries")
        
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        raise
    finally:
        conn.close()

def vacuum_database(**context):
    """Optimize database after cleanup"""
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB not available - skipping vacuum")
        return True
    
    db_path = '/data/observability.db'
    
    try:
        conn = duckdb.connect(db_path)
        
        # Analyze tables for query optimization
        conn.execute("ANALYZE service_metrics")
        conn.execute("ANALYZE anomalies")
        conn.execute("ANALYZE incident_summaries")
        
        logger.info("Database optimization completed")
        
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing database: {e}")
        raise
    finally:
        conn.close()

# Default arguments
default_args = {
    'owner': 'observability',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define DAG
dag = DAG(
    'data_quality_cleanup',
    default_args=default_args,
    description='Validate data quality and cleanup old data',
    schedule_interval=timedelta(hours=6),  # Run every 6 hours
    catchup=False,
    tags=['data-quality', 'maintenance'],
)

# Task 1: Validate metrics data
validate_data = PythonOperator(
    task_id='validate_metrics_data',
    python_callable=validate_metrics_data,
    dag=dag,
)

# Task 2: Cleanup old data
cleanup_data = PythonOperator(
    task_id='cleanup_old_data',
    python_callable=cleanup_old_data,
    dag=dag,
)

# Task 3: Vacuum database
vacuum_db = PythonOperator(
    task_id='vacuum_database',
    python_callable=vacuum_database,
    dag=dag,
)

# Define task dependencies
validate_data >> cleanup_data >> vacuum_db
