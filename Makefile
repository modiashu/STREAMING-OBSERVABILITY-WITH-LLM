.PHONY: help init start stop restart logs health clean

# Default target
help:
	@echo "Streaming Observability Platform - Make Commands"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "Production (Container-based):"
	@echo "  make init       - Initialize the platform (create dirs, DB schema)"
	@echo "  make start      - Start all services in containers"
	@echo "  make stop       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs (all services)"
	@echo "  make health     - Check service health"
	@echo "  make clean      - Clean up data and containers"
	@echo ""
	@echo "Development (Local venv):"
	@echo "  make dev-setup          - Setup development environment with UV"
	@echo "  make dev-activate       - Show activation command"
	@echo "  make dev-status         - Check dev environment status"
	@echo "  make dev-format         - Format code with black"
	@echo "  make dev-lint           - Lint code with ruff"
	@echo "  make dev-test           - Run tests"
	@echo "  make dev-test-db        - Test database locally"
	@echo "  make dev-clean          - Clean development environment"
	@echo "  make dev-clean-checkpoints - Clean Spark checkpoints (fresh start)"
	@echo "  make dev-clean-data     - Clean database and all data"
	@echo ""
	@echo "Individual service logs:"
	@echo "  make logs-events     - Event generator logs"
	@echo "  make logs-spark      - Spark streaming logs"
	@echo "  make logs-anomaly    - Anomaly detector logs"
	@echo "  make logs-llm        - LLM narrator logs"
	@echo "  make logs-dashboard  - Dashboard logs"
	@echo ""

# Initialize platform
init:
	@echo "Initializing platform..."
	@./scripts/init.sh

# Start all services
start:
	@echo "Starting all services..."
	@podman-compose up -d
	@echo ""
	@echo "Services starting... This may take 2-3 minutes."
	@echo "Run 'make health' to check status."
	@echo ""
	@echo "Access points:"
	@echo "  Dashboard: http://localhost:8501"
	@echo "  Airflow:   http://localhost:8080 (admin/admin)"

# Stop all services
stop:
	@echo "Stopping all services..."
	@podman-compose down

# Restart all services
restart: stop start

# View all logs
logs:
	@podman-compose logs -f

# View specific service logs
logs-events:
	@podman-compose logs -f event-generator

logs-spark:
	@podman-compose logs -f spark-streaming

logs-anomaly:
	@podman-compose logs -f anomaly-detector

logs-llm:
	@podman-compose logs -f llm-narrator

logs-dashboard:
	@podman-compose logs -f dashboard

logs-airflow:
	@podman-compose logs -f airflow-webserver airflow-scheduler

# Check service health
health:
	@./scripts/health_check.sh

# Clean up everything
clean:
	@echo "WARNING: This will remove all data and containers!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping services..."
	@podman-compose down -v
	@echo "Removing data..."
	@rm -rf ./data/*.db ./data/checkpoints/* ./data/logs/*
	@echo "Cleanup completed."

# Development targets (venv + UV)
dev-setup:
	@echo "Setting up development environment with UV..."
	@./scripts/setup_dev.sh

dev-activate:
	@echo "To activate the development environment, run:"
	@echo "  source .venv/bin/activate"

dev-format:
	@echo "Formatting code with black..."
	@.venv/bin/black .

dev-lint:
	@echo "Linting code with ruff..."
	@.venv/bin/ruff check .

dev-test:
	@echo "Running tests..."
	@.venv/bin/pytest tests/ -v

dev-test-db:
	@echo "Testing database initialization..."
	@.venv/bin/python scripts/init_db.py
	@echo "✓ Database initialized at ./data/observability.db"

dev-clean:
	@echo "Cleaning development environment..."
	@rm -rf .venv/
	@rm -rf .pytest_cache/
	@rm -rf .ruff_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@echo "✓ Development environment cleaned"

# Development helpers
dev-check-kafka:
	@echo "Checking Kafka container status..."
	@podman ps | grep -q kafka && echo "✓ Kafka is running" || echo "✗ Kafka is not running. Run: podman-compose up -d kafka"

dev-check-ollama:
	@echo "Checking Ollama container status..."
	@podman ps | grep -q ollama && echo "✓ Ollama is running" || echo "✗ Ollama is not running. Run: podman-compose up -d ollama"

dev-check-db:
	@echo "Checking DuckDB database..."
	@test -f ./data/observability.db && echo "✓ Database exists at ./data/observability.db" || echo "✗ Database not found. Run: python scripts/init_db.py"

dev-status:
	@echo "=== Development Environment Status ==="
	@echo ""
	@make dev-check-kafka
	@make dev-check-ollama
	@make dev-check-db
	@echo ""
	@echo "Python environment:"
	@test -d .venv && echo "✓ Virtual environment exists" || echo "✗ Virtual environment not found. Run: make dev-setup"
	@echo ""
	@echo "To run services locally, see: DEVELOPMENT.md"

dev-clean-checkpoints:
	@echo "Cleaning Spark checkpoints (for fresh start)..."
	@rm -rf ./data/checkpoints
	@echo "✓ Checkpoints cleaned. Spark will read from beginning."

dev-clean-data:
	@echo "WARNING: This will remove the database and all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@rm -f ./data/observability.db
	@rm -rf ./data/checkpoints
	@echo "✓ Data cleaned. Run 'python scripts/init_db.py' to recreate database."

