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

# Copy requirements first for better caching
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application code

# Copy application code
COPY src/ ./src/
COPY static/ ./static/


# Create app user/group, then HuggingFace cache dir and set permissions
RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /tmp/huggingface_cache \
    && chown -R app:app /tmp/huggingface_cache

EXPOSE 8002
EXPOSE 9101

# Copy and use shell script as entrypoint
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
USER app
CMD ["/app/start.sh"]
