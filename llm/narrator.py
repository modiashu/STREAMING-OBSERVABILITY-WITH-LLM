"""
LLM Incident Narrator Service
Generates human-readable explanations for detected anomalies using local LLM
Uses aggregated metrics only, never raw events
"""

import os
import time
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
import duckdb
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LLMNarrator:
    """Generate incident narratives using local LLM"""
    
    def __init__(self, db_path: str, ollama_url: str, model: str):
        """
        Initialize LLM narrator
        
        Args:
            db_path: Path to DuckDB database
            ollama_url: Ollama API URL
            model: Model name to use
        """
        self.db_path = db_path
        self.ollama_url = ollama_url
        self.model = model
        
    def _get_connection(self, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """Get database connection with retry on lock errors"""

        max_retries = 5
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                return duckdb.connect(self.db_path, read_only=read_only)
            except Exception as e:
                if "Could not set lock" in str(e) and attempt < max_retries - 1:
                    logger.debug(f"DB lock conflict, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
    
    def _get_unprocessed_anomalies(self) -> List[Dict]:
        """Fetch anomalies without incident summaries"""
        conn = self._get_connection()
        
        try:
            query = """
                SELECT 
                    a.id,
                    a.detected_at,
                    a.window_start,
                    a.window_end,
                    a.service,
                    a.anomaly_type,
                    a.severity,
                    a.metric_name,
                    a.metric_value,
                    a.baseline_value,
                    a.threshold_value,
                    a.description
                FROM anomalies a
                LEFT JOIN incident_summaries i ON a.id = i.anomaly_id
                WHERE i.id IS NULL
                AND a.detected_at >= CURRENT_TIMESTAMP - INTERVAL '10 minutes'
                ORDER BY a.detected_at DESC
                LIMIT 5
            """
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            anomalies = []
            for row in results:
                anomalies.append(dict(zip(columns, row)))
            
            return anomalies
            
        finally:
            conn.close()
    
    def _get_related_metrics(self, service: str, window_start, window_end) -> Optional[Dict]:
        """Get metrics for the anomaly window"""
        conn = self._get_connection()
        
        try:
            query = """
                SELECT 
                    request_count,
                    error_count,
                    error_rate,
                    avg_latency_ms,
                    p95_latency_ms,
                    p99_latency_ms
                FROM service_metrics
                WHERE service = ?
                AND window_start = ?
                AND window_end = ?
            """
            
            result = conn.execute(query, [service, window_start, window_end]).fetchone()
            
            if result:
                columns = [desc[0] for desc in conn.description]
                return dict(zip(columns, result))
            
            return None
            
        finally:
            conn.close()
    
    def _build_prompt(self, anomaly: Dict, metrics: Optional[Dict]) -> str:
        """
        Build prompt for LLM
        
        Args:
            anomaly: Anomaly record
            metrics: Related metrics
            
        Returns:
            Formatted prompt
        """
        window_start = anomaly['window_start'].strftime('%Y-%m-%d %H:%M:%S')
        window_end = anomaly['window_end'].strftime('%Y-%m-%d %H:%M:%S')
        
        prompt = f"""You are a production observability assistant. Analyze this incident and provide a concise explanation.

Time Window: {window_start} to {window_end} UTC
Service: {anomaly['service']}
Anomaly Type: {anomaly['anomaly_type']}
Severity: {anomaly['severity']}

Metrics for this window:
"""
        
        if metrics:
            prompt += f"""- Total Requests: {metrics['request_count']}
- Error Count: {metrics['error_count']}
- Error Rate: {metrics['error_rate']:.2%}
- Avg Latency: {metrics['avg_latency_ms']:.1f}ms
- P95 Latency: {metrics['p95_latency_ms']:.1f}ms
- P99 Latency: {metrics['p99_latency_ms']:.1f}ms
"""
        
        if anomaly['baseline_value']:
            prompt += f"\nBaseline {anomaly['metric_name']}: {anomaly['baseline_value']:.2f}"
        
        prompt += f"""
Current {anomaly['metric_name']}: {anomaly['metric_value']:.2f}
Threshold: {anomaly['threshold_value']:.2f}

Provide:
1. A brief (2-3 sentence) explanation of what happened
2. 2-3 possible root causes
3. Recommended immediate actions

Keep response concise and technical. Focus on actionable information."""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Call local LLM via Ollama API
        
        Args:
            prompt: Input prompt
            
        Returns:
            LLM response or None
        """
        try:
            url = f"{self.ollama_url}/api/generate"
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Low temperature for consistent, factual responses
                    "num_predict": 300   # Limit response length
                }
            }
            
            logger.info(f"Calling LLM: {self.model}")
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '').strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API call failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None
    
    def _parse_llm_response(self, response: str) -> Dict[str, str]:
        """
        Parse LLM response into structured format
        
        Args:
            response: Raw LLM response
            
        Returns:
            Dict with summary and possible_causes
        """
        lines = response.split('\n')
        
        summary = []
        causes = []
        actions = []
        
        current_section = summary
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            lower_line = line.lower()
            if 'possible' in lower_line and ('cause' in lower_line or 'root' in lower_line):
                current_section = causes
                continue
            elif 'recommend' in lower_line or 'action' in lower_line:
                current_section = actions
                continue
            
            # Add line to current section
            current_section.append(line)
        
        return {
            'summary': ' '.join(summary) if summary else response[:200],
            'possible_causes': ' '.join(causes) if causes else 'Multiple potential factors may have contributed to this anomaly.',
            'recommended_actions': ' '.join(actions) if actions else 'Monitor service health and investigate underlying infrastructure.'
        }
    
    def _save_incident_summary(self, anomaly: Dict, llm_response: str, parsed: Dict):
        """Save generated incident summary to database"""
        conn = self._get_connection()
        
        try:
            # Combine summary and causes for the main summary field
            full_summary = f"{parsed['summary']} {parsed['recommended_actions']}"
            
            conn.execute("""
                INSERT INTO incident_summaries (
                    id, anomaly_id, service, time_window_start, time_window_end,
                    summary, possible_causes, affected_metrics, llm_model
                ) VALUES (
                    nextval('seq_incident_summaries_id'), ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                anomaly['id'],
                anomaly['service'],
                anomaly['window_start'],
                anomaly['window_end'],
                full_summary,
                parsed['possible_causes'],
                anomaly['metric_name'],
                self.model
            ])
            
            conn.commit()
            logger.info(f"Saved incident summary for anomaly {anomaly['id']}")
            
        finally:
            conn.close()
    
    def process_anomalies(self):
        """Process unprocessed anomalies and generate summaries"""
        logger.info("Checking for unprocessed anomalies...")
        
        anomalies = self._get_unprocessed_anomalies()
        
        if not anomalies:
            logger.info("No new anomalies to process")
            return
        
        logger.info(f"Found {len(anomalies)} anomalies to process")
        
        for anomaly in anomalies:
            try:
                logger.info(
                    f"Processing anomaly {anomaly['id']}: "
                    f"{anomaly['severity']} {anomaly['anomaly_type']} in {anomaly['service']}"
                )
                
                # Get related metrics
                metrics = self._get_related_metrics(
                    anomaly['service'],
                    anomaly['window_start'],
                    anomaly['window_end']
                )
                
                # Build prompt
                prompt = self._build_prompt(anomaly, metrics)
                
                # Call LLM
                llm_response = self._call_llm(prompt)
                
                if not llm_response:
                    logger.warning(f"No LLM response for anomaly {anomaly['id']}, skipping")
                    continue
                
                logger.info(f"LLM response received ({len(llm_response)} chars)")
                
                # Parse response
                parsed = self._parse_llm_response(llm_response)
                
                # Save to database
                self._save_incident_summary(anomaly, llm_response, parsed)
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing anomaly {anomaly['id']}: {e}")
                continue
    
    def run(self, check_interval: int = 60):
        """
        Run narrator loop
        
        Args:
            check_interval: Seconds between checks
        """
        logger.info(f"Starting LLM narrator (check every {check_interval}s)")
        logger.info(f"Using model: {self.model} at {self.ollama_url}")
        
        try:
            while True:
                self.process_anomalies()
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("LLM narrator stopped by user")
        except Exception as e:
            logger.error(f"LLM narrator error: {e}")
            raise

def main():
    """Main entry point"""
    db_path = os.getenv('DUCKDB_PATH', '/data/observability.db')
    ollama_url = os.getenv('OLLAMA_URL', 'http://ollama:11434')
    model = os.getenv('OLLAMA_MODEL', 'phi')
    check_interval = int(os.getenv('CHECK_INTERVAL_SECONDS', '60'))
    
    logger.info(f"Configuration:")
    logger.info(f"  Database: {db_path}")
    logger.info(f"  Ollama URL: {ollama_url}")
    logger.info(f"  Model: {model}")
    logger.info(f"  Check Interval: {check_interval}s")
    
    # Wait for Ollama and initial anomalies
    logger.info("Waiting for Ollama to be ready...")
    time.sleep(20)
    
    narrator = LLMNarrator(db_path, ollama_url, model)
    narrator.run(check_interval=check_interval)

if __name__ == '__main__':
    main()
