"""
Observability Platform Monitoring DAG
Monitors the health of streaming pipeline components
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import logging

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logging.warning("DuckDB not installed - DAG will run in dummy mode")

logger = logging.getLogger(__name__)

def check_kafka_lag(**context):
    """Check if Kafka consumers are keeping up"""
    # In production, you would check Kafka consumer lag
    # For this demo, we'll do a simple health check
    logger.info("Checking Kafka consumer lag...")
    # Placeholder for actual Kafka lag check
    return True

def check_metrics_freshness(**context):
    """Check if metrics are being written recently"""
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB not available - skipping freshness check")
        return True
    
    db_path = '/data/observability.db'
    
    try:
        conn = duckdb.connect(db_path)
        
        # Check for recent metrics (last 5 minutes)
        result = conn.execute("""
            SELECT COUNT(*) as count
            FROM service_metrics
            WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '5 minutes'
        """).fetchone()
        
        count = result[0] if result else 0
        
        logger.info(f"Found {count} recent metric records")
        
        if count == 0:
            logger.warning("No recent metrics found!")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking metrics freshness: {e}")
        return False
    finally:
        conn.close()

def check_anomaly_detection(**context):
    """Verify anomaly detection is running"""
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB not available - skipping anomaly detection check")
        return True
    
    db_path = '/data/observability.db'
    
    try:
        conn = duckdb.connect(db_path)
        
        # Check for recent anomaly checks (anomalies table updates)
        result = conn.execute("""
            SELECT COUNT(*) as count
            FROM anomalies
            WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '10 minutes'
        """).fetchone()
        
        count = result[0] if result else 0
        
        logger.info(f"Found {count} anomalies detected in last 10 minutes")
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking anomaly detection: {e}")
        return False
    finally:
        conn.close()

def generate_health_report(**context):
    """Generate overall health report"""
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB not available - generating dummy health report")
        logger.info("=== Platform Health Report (Dummy Mode) ===")
        logger.info("DuckDB not installed - monitoring in limited mode")
        logger.info("All checks passed in dummy mode")
        logger.info("===========================================")
        return True
    
    db_path = '/data/observability.db'
    
    try:
        conn = duckdb.connect(db_path)
        
        # Get summary statistics
        metrics_count = conn.execute("""
            SELECT COUNT(*) FROM service_metrics
        """).fetchone()[0]
        
        anomalies_count = conn.execute("""
            SELECT COUNT(*) FROM anomalies
        """).fetchone()[0]
        
        summaries_count = conn.execute("""
            SELECT COUNT(*) FROM incident_summaries
        """).fetchone()[0]
        
        recent_services = conn.execute("""
            SELECT DISTINCT service
            FROM service_metrics
            WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '5 minutes'
        """).fetchall()
        
        logger.info("=== Platform Health Report ===")
        logger.info(f"Total Metrics Records: {metrics_count}")
        logger.info(f"Total Anomalies: {anomalies_count}")
        logger.info(f"Total Incident Summaries: {summaries_count}")
        logger.info(f"Active Services: {[s[0] for s in recent_services]}")
        logger.info("=============================")
        
        # Push to XCom for downstream tasks
        context['ti'].xcom_push(key='health_report', value={
            'metrics_count': metrics_count,
            'anomalies_count': anomalies_count,
            'summaries_count': summaries_count,
            'active_services': [s[0] for s in recent_services]
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Error generating health report: {e}")
        return False
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
    'retry_delay': timedelta(minutes=2),
}

# Define DAG
dag = DAG(
    'observability_monitoring',
    default_args=default_args,
    description='Monitor observability platform health',
    schedule_interval=timedelta(minutes=5),  # Run every 5 minutes
    catchup=False,
    tags=['monitoring', 'observability'],
)

# Task 1: Check Kafka lag
check_kafka = PythonOperator(
    task_id='check_kafka_lag',
    python_callable=check_kafka_lag,
    dag=dag,
)

# Task 2: Check metrics freshness
check_metrics = PythonOperator(
    task_id='check_metrics_freshness',
    python_callable=check_metrics_freshness,
    dag=dag,
)

# Task 3: Check anomaly detection
check_anomalies = PythonOperator(
    task_id='check_anomaly_detection',
    python_callable=check_anomaly_detection,
    dag=dag,
)

# Task 4: Generate health report
health_report = PythonOperator(
    task_id='generate_health_report',
    python_callable=generate_health_report,
    dag=dag,
)

# Define task dependencies
[check_kafka, check_metrics, check_anomalies] >> health_report
