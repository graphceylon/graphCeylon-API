# GraphCeylon-API Project Structure

## Directory Structure

```
graphCeylon-API/
├── .github/                          # GitHub specific files
│   ├── workflows/                    # CI/CD workflows
│   │   └── ci-cd.yaml               # Main CI/CD pipeline
│   ├── ISSUE_TEMPLATE/              # Issue templates
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── pull_request_template.md     # PR template
│
├── services/                         # Microservices
│   ├── language_service/            # Component 1: Multilingual NLP
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── main.py             # FastAPI application
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_main.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   ├── kg_service/                  # Component 2: Knowledge Graph
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_main.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   ├── recommender_service/         # Component 3: Recommendations
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_main.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   └── orchestrator/                # Component 4: Orchestration
│       ├── src/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── tests/
│       │   ├── __init__.py
│       │   └── test_main.py
│       ├── requirements.txt
│       └── .env.example
│
├── docker/                          # Docker configurations
│   ├── language_service/
│   │   └── Dockerfile
│   ├── kg_service/
│   │   └── Dockerfile
│   ├── recommender_service/
│   │   └── Dockerfile
│   └── orchestrator/
│       └── Dockerfile
│
├── infra/                           # Infrastructure as Code
│   ├── docker-compose.yaml         # Local development stack
│   └── k8s/                        # Kubernetes manifests (future)
│
├── configs/                         # Configuration files
│   ├── language_service/
│   ├── kg_service/
│   ├── recommender_service/
│   └── orchestrator/
│
├── data/                            # Data storage (gitignored)
│   ├── language_service/
│   │   ├── raw/
│   │   └── processed/
│   ├── kg_service/
│   │   ├── raw/
│   │   └── processed/
│   ├── recommender_service/
│   │   ├── raw/
│   │   └── processed/
│   └── orchestrator/
│       ├── raw/
│       └── processed/
│
├── models/                          # ML models (gitignored)
│   ├── language_service/
│   ├── kg_service/
│   ├── recommender_service/
│   └── orchestrator/
│
├── docs/                            # Documentation
│   ├── README.md
│   └── getting-started.md
│
├── scripts/                         # Utility scripts
│   └── setup-dev.ps1               # Development setup
│
├── .gitignore                       # Git ignore rules
├── CONTRIBUTING.md                  # Contribution guidelines
├── LICENSE                          # MIT License
└── README.md                        # Main project README
```

## Component Ports

- **Orchestrator**: 8002 (API Gateway)
- **Language Service**: 8001
- **Knowledge Graph Service**: 8000
- **Recommender Service**: 8003

## Technology Stack per Component

### Language Service (Port 8001)

- FastAPI
- Transformers
- PyTorch
- Spacy
- NLTK

### Knowledge Graph Service (Port 8000)

- FastAPI
- NetworkX
- Pandas
- NumPy

### Recommender Service (Port 8003)

- FastAPI
- Scikit-learn
- PyTorch
- LightFM

### Orchestrator (Port 8002)

- FastAPI
- HTTPX
- OpenTelemetry

## Data Flow

```
User Request
    ↓
Orchestrator (8002)
    ↓
┌───┴──────┬──────────┬─────────────┐
│          │          │             │
Language   KG      Recommender   External
(8001)   (8000)     (8003)        APIs
│          │          │             │
└───┬──────┴──────────┴─────────────┘
    ↓
Response via Orchestrator
```

## Getting Started

1. **Clone the repository**

```bash
git clone <repo-url>
cd graphCeylon-API
```

2. **Set up development environment**

```powershell
.\scripts\setup-dev.ps1
```

3. **Run with Docker Compose**

```bash
docker-compose -f infra/docker-compose.yaml up
```

## Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes in your service
3. Write tests
4. Run tests: `pytest`
5. Commit: `git commit -m "feat(service): description"`
6. Push and create PR

## Team Responsibilities

### Language Service Team

- Multilingual NLP
- Language detection
- Entity extraction
- Intent recognition

### Knowledge Graph Team

- Graph schema design
- Query optimization
- Knowledge base curation
- Entity relationships

### Recommender Team

- Recommendation algorithms
- Sustainability metrics
- User preference modeling
- Context awareness

### Orchestrator Team

- API gateway
- Service coordination
- Authentication
- Rate limiting
- Monitoring

## Documentation Links

- [Main README](../README.md)
- [Getting Started](getting-started.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [API Documentation](api.md)

---

Last updated: December 2025
