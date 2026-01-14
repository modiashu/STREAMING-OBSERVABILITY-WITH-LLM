#!/bin/bash

# Initialization script for the observability platform
# This script sets up the environment and initializes the database

set -e

echo "================================="
echo "Observability Platform Setup"
echo "================================="

# Create data directory
echo "Creating data directory..."
mkdir -p ./data
mkdir -p ./data/checkpoints
mkdir -p ./data/logs

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
fi

# Initialize DuckDB database
echo "Initializing DuckDB database..."
python3 scripts/init_db.py

echo ""
echo "================================="
echo "Setup completed successfully!"
echo "================================="
echo ""
echo "To start the platform, run:"
echo "  podman-compose up -d"
echo ""
echo "Access points:"
echo "  - Dashboard: http://localhost:8501"
echo "  - Airflow: http://localhost:8080 (admin/admin)"
echo "  - Kafka: localhost:29092"
echo ""
