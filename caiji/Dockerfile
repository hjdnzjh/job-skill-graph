FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Data directories
RUN mkdir -p data/raw data/processed data/snapshots logs

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "main_web.py", "--host", "0.0.0.0", "--port", "8000"]
