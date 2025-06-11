FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from parent directory
COPY ../requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy congress_api code
COPY . congress_api/

CMD ["uvicorn", "congress_api.main:server.http_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]