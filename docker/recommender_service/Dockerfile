FROM python:3.11-slim

WORKDIR /app

# System deps + uv
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

# ---- Python deps for THIS service ----
COPY services/recommender_service/requirements.txt .
RUN uv pip install --system -r requirements.txt

# ---- Copy application code ----
# This creates /app/src/...
COPY services/recommender_service/src ./src

# If you have local models/data for this service:
# COPY models/recommender_service ./models
# COPY data/recommender_service ./data

# So that the top-level /app is on sys.path and "src.*" imports work
ENV PYTHONPATH=/app

EXPOSE 8003

# IMPORTANT: use the full module path to your app
# your file is src/api/main.py → module "src.api.main"
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8003"]
