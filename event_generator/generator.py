"""
Event Generator Service
Simulates service telemetry and publishes events to Kafka
Supports configurable anomaly injection for testing
"""

import json
import time
import random
import logging

from datetime import datetime, timezone
from typing import Dict, List
from kafka import KafkaProducer
from kafka.errors import KafkaError
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventGenerator:
    """Generates realistic service telemetry events"""
    
    SERVICES = ['checkout', 'payments', 'search']
    ENDPOINTS = {
        'checkout': ['/api/cart', '/api/checkout', '/api/cart/items'],
        'payments': ['/api/payment/process', '/api/payment/validate', '/api/refund'],
        'search': ['/api/search', '/api/autocomplete', '/api/filters']
    }
    
    # Normal baseline metrics
    BASELINE_LATENCY = {
        'checkout': 150,
        'payments': 200,
        'search': 50
    }
    
    BASELINE_ERROR_RATE = 0.02  # 2% error rate
    
    def __init__(self, kafka_broker: str, topic: str, anomaly_probability: float = 0.05):
        """
        Initialize event generator
        
        Args:
            kafka_broker: Kafka broker address
            topic: Topic to publish events
            anomaly_probability: Probability of injecting anomalies (0-1)
        """
        self.kafka_broker = kafka_broker
        self.topic = topic
        self.anomaly_probability = anomaly_probability
        self.producer = None
        self.anomaly_active = False
        self.anomaly_service = None
        self.anomaly_type = None
        self.anomaly_start_time = None
        
    def connect(self):
        """Connect to Kafka broker"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version=(2, 5, 0)
            )
            logger.info(f"Connected to Kafka broker: {self.kafka_broker}")
        except KafkaError as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def _should_inject_anomaly(self) -> bool:
        """Determine if we should inject an anomaly"""
        if self.anomaly_active:
            # Keep anomaly active for 2-5 minutes
            duration = time.time() - self.anomaly_start_time
            if duration > random.randint(120, 300):
                logger.info(f"Ending anomaly: {self.anomaly_type} on {self.anomaly_service}")
                self.anomaly_active = False
                self.anomaly_service = None
                self.anomaly_type = None
                return False
            return True
        else:
            # Random chance to start new anomaly
            if random.random() < self.anomaly_probability:
                self.anomaly_active = True
                self.anomaly_service = random.choice(self.SERVICES)
                self.anomaly_type = random.choice(['latency_spike', 'error_surge'])
                self.anomaly_start_time = time.time()
                logger.warning(f"Starting anomaly: {self.anomaly_type} on {self.anomaly_service}")
                return True
        return False
    
    def _generate_event(self) -> Dict:
        """Generate a single telemetry event"""
        service = random.choice(self.SERVICES)
        endpoint = random.choice(self.ENDPOINTS[service])
        
        # Determine if this event should be part of an anomaly
        is_anomalous = False
        if self._should_inject_anomaly() and service == self.anomaly_service:
            is_anomalous = True
        
        # Generate latency
        baseline_latency = self.BASELINE_LATENCY[service]
        if is_anomalous and self.anomaly_type == 'latency_spike':
            # 5-10x normal latency during spike
            latency_ms = int(baseline_latency * random.uniform(5, 10))
        else:
            # Normal latency with some variance
            latency_ms = int(random.gauss(baseline_latency, baseline_latency * 0.2))
            latency_ms = max(10, latency_ms)  # Ensure positive
        
        # Generate status code
        if is_anomalous and self.anomaly_type == 'error_surge':
            # 20-40% error rate during surge
            error_probability = random.uniform(0.2, 0.4)
        else:
            error_probability = self.BASELINE_ERROR_RATE
        
        if random.random() < error_probability:
            status_code = random.choice([500, 503, 504, 429])
        else:
            status_code = random.choice([200, 201, 204])
        

        event = {
            'event_time': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'service': service,
            'endpoint': endpoint,
            'latency_ms': latency_ms,
            'status_code': status_code
        }
        
        return event
    
    def run(self, events_per_second: int = 10):
        """
        Start generating and publishing events
        
        Args:
            events_per_second: Rate of event generation
        """
        if not self.producer:
            self.connect()
        
        logger.info(f"Starting event generation: {events_per_second} events/sec")
        
        interval = 1.0 / events_per_second
        
        try:
            while True:
                event = self._generate_event()
                
                # Publish to Kafka
                future = self.producer.send(self.topic, value=event)
                
                # Log occasionally
                if random.random() < 0.01:  # Log ~1% of events
                    logger.info(f"Event published: {event}")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Shutting down event generator")
        except Exception as e:
            logger.error(f"Error generating events: {e}")
            raise
        finally:
            if self.producer:
                self.producer.flush()
                self.producer.close()

def main():
    """Main entry point"""
    kafka_broker = os.getenv('KAFKA_BROKER', 'kafka:9092')
    topic = os.getenv('KAFKA_RAW_EVENTS_TOPIC', 'raw_events')
    anomaly_prob = float(os.getenv('ANOMALY_PROBABILITY', '0.05'))
    events_per_sec = int(os.getenv('EVENTS_PER_SECOND', '10'))
    
    logger.info(f"Configuration:")
    logger.info(f"  Kafka Broker: {kafka_broker}")
    logger.info(f"  Topic: {topic}")
    logger.info(f"  Anomaly Probability: {anomaly_prob}")
    logger.info(f"  Events/sec: {events_per_sec}")
    
    # Wait for Kafka to be ready
    logger.info("Waiting for Kafka to be ready...")
    time.sleep(10)
    
    generator = EventGenerator(kafka_broker, topic, anomaly_prob)
    generator.run(events_per_second=events_per_sec)

if __name__ == '__main__':
    main()
