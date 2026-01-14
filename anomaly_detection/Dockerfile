FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir duckdb==0.9.2

# Copy application code
COPY detector.py .

# Run the detector
CMD ["python", "-u", "detector.py"]
