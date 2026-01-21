FROM python:3.12-slim

WORKDIR /app

COPY ../../services/profile_agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ../../services/profile_agent /app

ENV PYTHONPATH=/app

EXPOSE 8007

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8007"]
