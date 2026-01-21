FROM python:3.11-slim

WORKDIR /app

# system deps if needed
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY src ./src

EXPOSE 8003
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8003"]
