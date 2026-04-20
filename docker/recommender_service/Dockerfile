FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Copy requirements first for better caching
COPY services/recommender_service/requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY services/recommender_service/src/ ./src/

# Copy configs from repo root (required: service imports configs.recommender_service.config)
COPY configs/ ./configs/

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app
USER app

EXPOSE 8003

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8003"]
