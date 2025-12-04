# Getting Started - Team Onboarding Guide

Welcome to the GraphCeylon-API project! This guide will help you get set up and start contributing.

## 🚀 Quick Setup (5 minutes)

### 1. Install Prerequisites

**Install uv (Package Manager):**

```powershell
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install Git:**

- Download from [git-scm.com](https://git-scm.com/)

### 2. Clone the Repository

```bash
git clone <repository-url>
cd graphCeylon-API
```

### 3. Choose Your Component

Pick which service you'll be working on:

- **Language Service** (Port 8001) - Multilingual NLP
- **Knowledge Graph Service** (Port 8000) - Graph & Knowledge Management
- **Recommender Service** (Port 8003) - AI Recommendations
- **Orchestrator** (Port 8002) - API Gateway & Coordination

### 4. Set Up Your Service

```bash
# Navigate to your service
cd services/language_service  # or kg_service, recommender_service, orchestrator

# Create virtual environment
uv venv

# Activate it
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Copy environment template
cp .env.example .env

# Install dependencies (once you add them to requirements.txt)
uv pip install -r requirements.txt
```

### 5. Start Development

```bash
# Run your service
python src/main.py
```

Your service should now be running! Check http://localhost:800X (where X is your service port)

---

## 📝 Development Workflow

### Step 1: Create a Feature Branch

```bash
# Make sure you're on develop branch
git checkout develop
git pull origin develop

# Create your feature branch
git checkout -b feature/your-feature-name
```

**Branch naming:**

- `feature/language-tamil-support`
- `fix/kg-query-timeout`
- `docs/update-api-guide`

### Step 2: Add Your Dependencies

Edit `requirements.txt` in your service directory:

```txt
# Example for Language Service
fastapi==0.104.1
uvicorn[standard]==0.24.0
transformers==4.35.2
torch==2.1.1
```

Then install:

```bash
uv pip install -r requirements.txt
```

### Step 3: Write Your Code

Create your modules in the `src/` directory:

```
services/your_service/
├── src/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── api/             # API endpoints
│   │   └── routes.py
│   ├── models/          # Data models
│   │   └── schemas.py
│   ├── services/        # Business logic
│   │   └── processor.py
│   └── utils/           # Utility functions
│       └── helpers.py
└── tests/
    └── test_main.py
```

### Step 4: Test Your Code

```bash
# Run tests
pytest

# Run with coverage
pytest --cov
```

### Step 5: Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with conventional commit message
git commit -m "feat(language): add Tamil language support"
```

**Commit message format:**

- `feat(service): description` - New feature
- `fix(service): description` - Bug fix
- `docs: description` - Documentation
- `test(service): description` - Tests
- `refactor(service): description` - Code refactoring

### Step 6: Push and Create Pull Request

```bash
# Push your branch
git push origin feature/your-feature-name
```

Then:

1. Go to GitHub repository
2. Click "New Pull Request"
3. Select `develop` as base branch
4. Fill in the PR template
5. Request review from team members

---

## 🛠️ Common Tasks

### Running Your Service

```bash
# Development mode (with auto-reload)
uvicorn src.main:app --reload --port 8001
```

### Adding a New Package

```bash
# Install the package
uv pip install package-name

# Add to requirements.txt
echo "package-name==version" >> requirements.txt
```

### Running All Services with Docker

```bash
# Build and start all services
docker-compose -f infra/docker-compose.yaml up --build

# Stop all services
docker-compose -f infra/docker-compose.yaml down
```

### Checking Service Health

```bash
# Language Service
curl http://localhost:8001/health

# Knowledge Graph
curl http://localhost:8000/health

# Recommender
curl http://localhost:8003/health

# Orchestrator
curl http://localhost:8002/health
```

---

## 📚 Project Structure

```
services/your_service/
├── src/                    # Source code
│   ├── main.py            # FastAPI app
│   ├── api/               # API routes
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   └── utils/             # Utilities
├── tests/                 # Test files
├── requirements.txt       # Dependencies
└── .env.example          # Environment template
```

---

## 🤝 Collaboration Guidelines

### Communication

- **Questions?** Open an issue or ask in team chat
- **Found a bug?** Create an issue with the bug template
- **Have an idea?** Create an issue with the feature request template

### Code Reviews

- Be respectful and constructive
- Focus on the code, not the person
- Explain the "why" behind suggestions
- Approve when satisfied

### Working Together

**If you need data from another service:**

1. Check their API documentation (http://localhost:800X/docs)
2. Coordinate with that team
3. Use the Orchestrator to make service-to-service calls

**Example:**

```python
# In your service
import httpx

async def get_language_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://language_service:8001/process")
        return response.json()
```

---

## 🔍 Troubleshooting

### Port Already in Use

```bash
# Windows - Find process using port
netstat -ano | findstr :8001

# Kill process
taskkill /PID <process-id> /F
```

### Virtual Environment Issues

```bash
# Remove and recreate
rm -rf .venv
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

### Docker Build Fails

```bash
# Clean rebuild
docker-compose -f infra/docker-compose.yaml build --no-cache
```

---

## 📖 Additional Resources

- [Main README](../README.md) - Project overview
- [UV Guide](uv-guide.md) - Package manager documentation
- [API Documentation](api.md) - API design guidelines
- [Contributing Guide](../CONTRIBUTING.md) - Detailed contribution guidelines
- [Project Structure](../PROJECT_STRUCTURE.md) - Complete structure reference

---

## 🎯 Your First Contribution

### Easy Tasks to Start With:

1. **Set up your service** - Get it running locally
2. **Add health check endpoint** - Already done in main.py!
3. **Write a simple test** - Add to tests/test_main.py
4. **Add your dependencies** - Update requirements.txt
5. **Create your first API endpoint** - Add a route in src/api/

### Example First Feature:

```python
# src/api/routes.py
from fastapi import APIRouter

router = APIRouter()

@router.post("/process")
async def process_data(data: dict):
    """Your first endpoint!"""
    return {
        "status": "success",
        "message": "Data processed",
        "data": data
    }
```

---

## 💬 Need Help?

- **Technical Issues**: Open a GitHub issue
- **Questions**: Ask in team chat
- **Setup Problems**: Check [Troubleshooting](#🔍-troubleshooting) section
- **Urgent**: Contact the team lead

---

**Welcome aboard! Let's build something amazing together! 🚀**
