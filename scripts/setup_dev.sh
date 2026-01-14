#!/bin/bash

# Development Environment Setup Script
# Sets up Python venv with UV package manager

set -e

# Load proxy settings from .env file if it exists (not committed to git)
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | grep -E 'HTTP_PROXY|HTTPS_PROXY|http_proxy|https_proxy' | xargs)
    echo ""
fi

echo "================================="
echo "Development Environment Setup"
echo "================================="
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "UV package manager not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo "UV installed. Please restart your shell or run:"
    echo "  source $HOME/.cargo/env"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✓ UV package manager found: $(uv --version)"
echo ""

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    uv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

echo ""

# Install dependencies using UV
echo "Installing dependencies with UV (this is fast!)..."
# Add --native-tls flag to use system certificates (better for corporate proxies)
UV_INDEX_STRATEGY=unsafe-best-match uv pip install --native-tls -e ".[dev]"

echo ""
echo "================================="
echo "Development Setup Complete!"
echo "================================="
echo ""
echo "To activate the environment:"
echo "  source .venv/bin/activate"
echo ""
echo "Development commands:"
echo "  make dev-test          # Run tests"
echo "  make dev-format        # Format code"
echo "  make dev-lint          # Lint code"
echo "  make dev-db            # Test database locally"
echo ""
echo "To run services locally (requires Kafka):"
echo "  python event_generator/generator.py"
echo "  python anomaly_detection/detector.py"
echo "  python llm/narrator.py"
echo "  streamlit run dashboard/app.py"
echo ""
