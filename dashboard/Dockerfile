FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    streamlit==1.29.0 \
    duckdb==0.9.2 \
    pandas==2.1.4 \
    plotly==5.18.0

# Copy application code
COPY app.py .

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
