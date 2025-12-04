# Quick Start Guide

This guide will help you get GraphCeylon-API up and running on your local machine.

## Prerequisites

Ensure you have the following installed:

- **Python 3.9+**
- **uv** (Package Manager) - [Installation Guide](uv-guide.md)
- **Docker** and **Docker Compose**
- **Git**

## Clone the Repository

```bash
git clone <repository-url>
cd graphCeylon-API
```

## Option 1: Run with Docker Compose (Recommended)

### Start all services

```bash
docker-compose -f infra/docker-compose.yaml up -d
```

This will start all 4 microservices.

### Verify services are running

```bash
docker-compose -f infra/docker-compose.yaml ps
```

### Access services

- **Orchestrator**: http://localhost:8002
- **Language Service**: http://localhost:8001
- **Knowledge Graph**: http://localhost:8000
- **Recommender**: http://localhost:8003

### View logs

```bash
# All services
docker-compose -f infra/docker-compose.yaml logs -f

# Specific service
docker-compose -f infra/docker-compose.yaml logs -f language_service
```

### Stop services

```bash
docker-compose -f infra/docker-compose.yaml down
```

## Option 2: Local Development Setup

### 1. Set up Language Service

```bash
cd services/language_service
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python src/main.py
```

### 2. Set up Knowledge Graph Service

```bash
cd services/kg_service
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python src/main.py
```

### 3. Set up Recommender Service

```bash
cd services/recommender_service
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python src/main.py
```

### 4. Set up Orchestrator

```bash
cd services/orchestrator
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python src/main.py
```

## Testing the Setup

### Health Check

```bash
# Check orchestrator
curl http://localhost:8002/health

# Check language service
curl http://localhost:8001/health

# Check KG service
curl http://localhost:8000/health

# Check recommender service
curl http://localhost:8003/health
```

### API Documentation

Each service provides interactive API documentation:

- http://localhost:8002/docs (Orchestrator)
- http://localhost:8001/docs (Language Service)
- http://localhost:8000/docs (Knowledge Graph)
- http://localhost:8003/docs (Recommender)

## Next Steps

- Read the [Architecture Documentation](architecture.md)
- Explore [API Documentation](api.md)
- Check out [Development Guide](development.md)
- Start [Contributing](../CONTRIBUTING.md)

## Troubleshooting

### Port conflicts

If ports are already in use, edit `infra/docker-compose.yaml` to change port mappings.

### Docker build issues

```bash
# Rebuild without cache
docker-compose -f infra/docker-compose.yaml build --no-cache
```

### Permission issues (Linux/Mac)

```bash
sudo chown -R $USER:$USER .
```

## Need Help?

- Check [docs/README.md](README.md) for more documentation
- Open an issue on GitHub
- Contact the team
