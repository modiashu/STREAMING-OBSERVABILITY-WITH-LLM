FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir duckdb==0.9.2 requests==2.31.0

# Copy application code
COPY narrator.py .

# Run the narrator
CMD ["python", "-u", "narrator.py"]
