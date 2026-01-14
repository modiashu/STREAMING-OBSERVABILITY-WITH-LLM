FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir kafka-python==2.0.2

# Copy application code
COPY generator.py .

# Run the generator
CMD ["python", "-u", "generator.py"]
