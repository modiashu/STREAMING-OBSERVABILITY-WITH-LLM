"""
Anomaly Detection Service
Rule-based anomaly detection on aggregated metrics
Detects latency spikes and error rate surges
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import duckdb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AnomalyDetector:
    """Rule-based anomaly detector"""
    
    # Detection thresholds
    ERROR_RATE_BASELINE = 0.05  # 5% baseline error rate
    ERROR_RATE_MULTIPLIER = 3.0  # Alert if 3x baseline
    
    LATENCY_THRESHOLDS = {
        'checkout': 300,   # 300ms SLA
        'payments': 400,   # 400ms SLA
        'search': 150      # 150ms SLA
    }
    
    LATENCY_MULTIPLIER = 2.0  # Alert if 2x SLA
    
    def __init__(self, db_path: str):
        """
        Initialize anomaly detector
        
        Args:
            db_path: Path to DuckDB database
        """
        self.db_path = db_path
        

    def _get_connection(self, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """Get database connection with retry on lock errors"""

        max_retries = 5
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            try:
                return duckdb.connect(self.db_path, read_only=read_only)
            except duckdb.IOException as e:
                if "Could not set lock" in str(e) and attempt < max_retries - 1:
                    logger.debug(f"DB lock conflict, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
    
    def _get_recent_metrics(self, minutes: int = 5) -> List[Dict]:
        """
        Fetch recent metrics from database
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            List of metric records
        """

        conn = self._get_connection(read_only=True)
        
        try:
            query = """
                SELECT 
                    window_start,
                    window_end,
                    service,
                    request_count,
                    error_count,
                    error_rate,
                    avg_latency_ms,
                    p95_latency_ms,
                    p99_latency_ms
                FROM service_metrics
                WHERE window_start >= CURRENT_TIMESTAMP - INTERVAL '? minutes'
                ORDER BY window_start DESC
            """
            
            # DuckDB doesn't support parameterized INTERVAL, so use string formatting
            query = query.replace('?', str(minutes))
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            metrics = []
            for row in results:
                metrics.append(dict(zip(columns, row)))
            
            return metrics
            
        finally:
            conn.close()
    
    def _get_baseline_metrics(self, service: str, hours: int = 1) -> Optional[Dict]:
        """
        Calculate baseline metrics for a service
        
        Args:
            service: Service name
            hours: Number of hours to calculate baseline
            
        Returns:
            Dict with baseline metrics or None
        """

        conn = self._get_connection(read_only=True)
        
        try:
            query = f"""
                SELECT 
                    AVG(error_rate) as avg_error_rate,
                    AVG(avg_latency_ms) as avg_latency,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_latency_ms) as median_latency
                FROM service_metrics
                WHERE service = ?
                AND window_start >= CURRENT_TIMESTAMP - INTERVAL '{hours} hours'
                AND window_start < CURRENT_TIMESTAMP - INTERVAL '5 minutes'
            """
            
            result = conn.execute(query, [service]).fetchone()
            
            if result and result[0] is not None:
                return {
                    'avg_error_rate': float(result[0]),
                    'avg_latency': float(result[1]),
                    'median_latency': float(result[2])
                }
            
            return None
            
        finally:
            conn.close()
    
    def _detect_error_rate_anomaly(
        self, 
        metric: Dict, 
        baseline: Optional[Dict]
    ) -> Optional[Tuple[str, str, float, float]]:
        """
        Detect error rate anomalies
        
        Returns:
            Tuple of (anomaly_type, severity, metric_value, threshold) or None
        """
        error_rate = metric['error_rate']
        
        # Use baseline if available, otherwise use default
        baseline_error_rate = (
            baseline['avg_error_rate'] if baseline 
            else self.ERROR_RATE_BASELINE
        )
        
        threshold = baseline_error_rate * self.ERROR_RATE_MULTIPLIER
        
        if error_rate > threshold and metric['request_count'] >= 10:
            # Determine severity
            if error_rate > threshold * 2:
                severity = 'critical'
            elif error_rate > threshold * 1.5:
                severity = 'high'
            else:
                severity = 'medium'
            
            return ('error_surge', severity, error_rate, threshold)
        
        return None
    
    def _detect_latency_anomaly(
        self, 
        metric: Dict, 
        baseline: Optional[Dict]
    ) -> Optional[Tuple[str, str, float, float]]:
        """
        Detect latency anomalies
        
        Returns:
            Tuple of (anomaly_type, severity, metric_value, threshold) or None
        """
        service = metric['service']
        avg_latency = metric['avg_latency_ms']
        
        # Get SLA threshold for service
        sla_threshold = self.LATENCY_THRESHOLDS.get(service, 200)
        threshold = sla_threshold * self.LATENCY_MULTIPLIER
        
        if avg_latency > threshold and metric['request_count'] >= 10:
            # Determine severity based on how far over threshold
            if avg_latency > threshold * 2:
                severity = 'critical'
            elif avg_latency > threshold * 1.5:
                severity = 'high'
            else:
                severity = 'medium'
            
            return ('latency_spike', severity, avg_latency, threshold)
        
        return None
    
    def _record_anomaly(
        self,
        metric: Dict,
        anomaly_type: str,
        severity: str,
        metric_name: str,
        metric_value: float,
        baseline_value: Optional[float],
        threshold_value: float,
        description: str
    ):
        """Record anomaly to database"""
        conn = self._get_connection()
        
        try:
            # Check if similar anomaly already exists (within same window)
            existing = conn.execute("""
                SELECT id FROM anomalies
                WHERE window_start = ?
                AND service = ?
                AND anomaly_type = ?
                AND resolved = FALSE
            """, [
                metric['window_start'],
                metric['service'],
                anomaly_type
            ]).fetchone()
            
            if existing:
                logger.debug(f"Anomaly already recorded for {metric['service']} at {metric['window_start']}")
                return
            
            # Insert new anomaly
            conn.execute("""
                INSERT INTO anomalies (
                    id, window_start, window_end, service, anomaly_type,
                    severity, metric_name, metric_value, baseline_value,
                    threshold_value, description, resolved
                ) VALUES (
                    nextval('seq_anomalies_id'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE
                )
            """, [
                metric['window_start'],
                metric['window_end'],
                metric['service'],
                anomaly_type,
                severity,
                metric_name,
                metric_value,
                baseline_value,
                threshold_value,
                description
            ])
            
            conn.commit()
            logger.warning(
                f"ANOMALY DETECTED: {severity.upper()} {anomaly_type} in {metric['service']} - {description}"
            )
            
        finally:
            conn.close()
    
    def detect_anomalies(self):
        """Run anomaly detection on recent metrics"""
        logger.info("Running anomaly detection...")
        
        # Fetch recent metrics
        metrics = self._get_recent_metrics(minutes=5)
        
        if not metrics:
            logger.info("No recent metrics found")
            return
        
        logger.info(f"Analyzing {len(metrics)} metric records")
        
        anomalies_detected = 0
        
        for metric in metrics:
            service = metric['service']
            
            # Get baseline for this service
            baseline = self._get_baseline_metrics(service, hours=1)
            
            # Detect error rate anomalies
            error_anomaly = self._detect_error_rate_anomaly(metric, baseline)
            if error_anomaly:
                anomaly_type, severity, value, threshold = error_anomaly
                description = (
                    f"Error rate {value:.2%} exceeds threshold {threshold:.2%} "
                    f"(baseline: {baseline['avg_error_rate']:.2%})" if baseline
                    else f"Error rate {value:.2%} exceeds threshold {threshold:.2%}"
                )
                
                self._record_anomaly(
                    metric=metric,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    metric_name='error_rate',
                    metric_value=value,
                    baseline_value=baseline['avg_error_rate'] if baseline else None,
                    threshold_value=threshold,
                    description=description
                )
                anomalies_detected += 1
            
            # Detect latency anomalies
            latency_anomaly = self._detect_latency_anomaly(metric, baseline)
            if latency_anomaly:
                anomaly_type, severity, value, threshold = latency_anomaly
                description = (
                    f"Avg latency {value:.1f}ms exceeds threshold {threshold:.1f}ms "
                    f"(baseline: {baseline['avg_latency']:.1f}ms)" if baseline
                    else f"Avg latency {value:.1f}ms exceeds threshold {threshold:.1f}ms"
                )
                
                self._record_anomaly(
                    metric=metric,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    metric_name='avg_latency_ms',
                    metric_value=value,
                    baseline_value=baseline['avg_latency'] if baseline else None,
                    threshold_value=threshold,
                    description=description
                )
                anomalies_detected += 1
        
        if anomalies_detected > 0:
            logger.info(f"Detected {anomalies_detected} anomalies")
        else:
            logger.info("No anomalies detected")
    
    def run(self, check_interval: int = 60):
        """
        Run anomaly detection loop
        
        Args:
            check_interval: Seconds between checks
        """
        logger.info(f"Starting anomaly detector (check every {check_interval}s)")
        
        try:
            while True:
                self.detect_anomalies()
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("Anomaly detector stopped by user")
        except Exception as e:
            logger.error(f"Anomaly detector error: {e}")
            raise

def main():
    """Main entry point"""

    db_path = os.getenv('DUCKDB_PATH', './data/observability.db')
    check_interval = int(os.getenv('CHECK_INTERVAL_SECONDS', '60'))
    
    logger.info(f"Configuration:")
    logger.info(f"  Database: {db_path}")
    logger.info(f"  Check Interval: {check_interval}s")
    
    # Wait for initial data
    logger.info("Waiting for initial metrics...")
    time.sleep(30)
    
    detector = AnomalyDetector(db_path)
    detector.run(check_interval=check_interval)

if __name__ == '__main__':
    main()
