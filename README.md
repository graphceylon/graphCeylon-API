# GraphCeylon-API

> A production-ready, microservices-based tourism intelligence platform for Sri Lanka, combining multilingual NLP, knowledge graphs, and AI-powered recommendations.

## 🚀 Quick Start for Team Members

**New to the project?** Start here: **[TEAM_ONBOARDING.md](TEAM_ONBOARDING.md)**

This guide will help you:

- ✅ Set up your development environment (5 minutes)
- ✅ Choose and configure your service
- ✅ Make your first contribution
- ✅ Understand the workflow

## 🏗️ Architecture Overview

GraphCeylon-API is built as a distributed system with 4 independent microservices:

### Component 1: Multilingual Language Service

- **Purpose**: Natural language processing and understanding for multiple languages (Sinhala, Tamil, English)
- **Location**: `services/language_service/`
- **Key Features**:
  - Multi-language text processing
  - Intent recognition
  - Entity extraction
  - Language translation

### Component 2: Tourism Knowledge Graph

- **Purpose**: Structured knowledge representation of Sri Lankan tourism domain
- **Location**: `services/kg_service/`
- **Key Features**:
  - Graph database management
  - Entity relationships
  - Query processing
  - Knowledge base maintenance

### Component 3: Proactive Recommendation & Sustainability Engine

- **Purpose**: Intelligent recommendation system with sustainability focus
- **Location**: `services/recommender_service/`
- **Key Features**:
  - Personalized recommendations
  - Sustainability scoring
  - User preference learning
  - Context-aware suggestions

### Component 4: Multi-Agent Orchestrator

- **Purpose**: Coordination layer managing service interactions and workflows
- **Location**: `services/orchestrator/`
- **Key Features**:
  - Service orchestration
  - Request routing
  - API gateway functionality
  - Inter-service communication

## 📁 Project Structure

```
graphCeylon-API/
├── services/                    # Microservices source code
│   ├── language_service/       # Component 1
│   ├── kg_service/            # Component 2
│   ├── recommender_service/   # Component 3
│   └── orchestrator/          # Component 4
├── docker/                     # Docker configurations per service
├── infra/                      # Infrastructure as Code
│   ├── docker-compose.yaml    # Local development
│   └── k8s/                   # Kubernetes manifests
├── configs/                    # Service configurations
├── data/                       # Data storage (gitignored)
├── models/                     # ML models (gitignored)
├── docs/                       # Documentation
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- uv (Package Manager) - See [UV Guide](docs/uv-guide.md)
- Docker & Docker Compose
- Git

### Clone the Repository

```bash
git clone <repository-url>
cd graphCeylon-API
```

### Development Setup

Each service can be developed independently:

#### Language Service

```bash
cd services/language_service
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

#### Knowledge Graph Service

```bash
cd services/kg_service
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

#### Recommender Service

```bash
cd services/recommender_service
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

#### Orchestrator

```bash
cd services/orchestrator
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### Running with Docker Compose

```bash
# Build all services
docker-compose -f infra/docker-compose.yaml build

# Start all services
docker-compose -f infra/docker-compose.yaml up

# Start specific service
docker-compose -f infra/docker-compose.yaml up language_service
```

## 🔧 Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `fix/*` - Bug fixes
- `release/*` - Release preparation

### Working on a Component

1. **Create feature branch**

```bash
git checkout -b feature/language-service-nlp-enhancement
```

2. **Make changes in your service**

```bash
cd services/language_service/
# Make your changes
```

3. **Test locally**

```bash
# Run service tests
pytest

# Test with Docker
docker-compose -f infra/docker-compose.yaml up language_service
```

4. **Commit and push**

```bash
git add .
git commit -m "feat(language): add Tamil language support"
git push origin feature/language-service-nlp-enhancement
```

5. **Create Pull Request** to `develop` branch

## 🧪 Testing

```bash
# Test individual service
cd services/<service_name>
pytest

# Test all services
./scripts/test-all.sh  # Create this script
```

## 📦 Deployment

### Development Environment

```bash
docker-compose -f infra/docker-compose.yaml up
```

### Production (Kubernetes)

```bash
kubectl apply -f infra/k8s/
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'feat: Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test additions/changes
- `chore:` - Build/tooling changes

## 📝 Documentation

Detailed documentation for each component:

- [Language Service Documentation](docs/language_service.md)
- [Knowledge Graph Documentation](docs/kg_service.md)
- [Recommender Service Documentation](docs/recommender_service.md)
- [Orchestrator Documentation](docs/orchestrator.md)
- [API Documentation](docs/api.md)
- [Deployment Guide](docs/deployment.md)

## 🛠️ Technology Stack

- **Language**: Python 3.9+
- **Web Framework**: FastAPI
- **Container**: Docker
- **Orchestration**: Kubernetes
- **CI/CD**: GitHub Actions

**Note**: Database solutions (Neo4j, MongoDB, Redis, etc.) can be added later as needed.

## 📊 Service Dependencies

```
┌─────────────────┐
│   Orchestrator  │  ← Entry point
└────────┬────────┘
         │
    ┌────┴─────┬─────────────┬────────────┐
    │          │             │            │
    ▼          ▼             ▼            ▼
┌────────┐ ┌────────┐ ┌────────────┐ ┌──────────┐
│Language│ │   KG   │ │Recommender │ │ External │
│Service │ │Service │ │  Service   │ │   APIs   │
└────────┘ └────────┘ └────────────┘ └──────────┘
```

## 🔐 Environment Variables

Create `.env` files for each service (see `.env.example` in each service directory):

```env
# Example for language_service
SERVICE_NAME=language_service
SERVICE_PORT=8001
LOG_LEVEL=INFO
MODEL_PATH=../../../models/language_service/
USE_GPU=false
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- Research Lead: [Name]
- Language Service: [Team Members]
- Knowledge Graph: [Team Members]
- Recommender System: [Team Members]
- Orchestrator: [Team Members]

**Note**: This is a research project. Ensure all data handling complies with privacy regulations and ethical guidelines.
