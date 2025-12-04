# Contributing to GraphCeylon-API

Thank you for your interest in contributing to the GraphCeylon-API project! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/graphCeylon-API.git
   cd graphCeylon-API
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/original-org/graphCeylon-API.git
   ```

## Development Workflow

### 1. Create a Feature Branch

Always create a new branch for your work:

```bash
git checkout develop
git pull upstream develop
git checkout -b feature/your-feature-name
```

Branch naming conventions:

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Adding or updating tests

### 2. Make Your Changes

- Write clean, readable code
- Follow Python PEP 8 style guide
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Commit Your Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```bash
git add .
git commit -m "feat(service-name): add new feature description"
```

Commit types:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:

```bash
git commit -m "feat(language): add Tamil language support"
git commit -m "fix(kg): resolve graph query timeout issue"
git commit -m "docs: update API documentation"
```

### 4. Keep Your Branch Updated

```bash
git fetch upstream
git rebase upstream/develop
```

### 5. Push Your Changes

```bash
git push origin feature/your-feature-name
```

### 6. Create a Pull Request

1. Go to your fork on GitHub
2. Click "New Pull Request"
3. Select `develop` as the base branch
4. Fill in the PR template with:
   - Description of changes
   - Related issue numbers
   - Testing performed
   - Screenshots (if applicable)

## Code Standards

### Python Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for functions and classes
- Keep functions small and focused
- Maximum line length: 100 characters

```python
def process_query(query: str, language: str = "en") -> dict:
    """
    Process a natural language query.

    Args:
        query: The input query string
        language: Language code (default: "en")

    Returns:
        dict: Processed query results
    """
    # Implementation
    pass
```

### Testing

- Write unit tests for new functionality
- Maintain test coverage above 80%
- Run tests before submitting PR:
  ```bash
  pytest tests/
  ```

### Documentation

- Update README.md if adding new features
- Add docstrings to all public functions/classes
- Update API documentation for endpoint changes
- Include usage examples

## Component-Specific Guidelines

### Language Service

- Test with multiple languages (Sinhala, Tamil, English)
- Include language detection tests
- Document NLP model versions used

### Knowledge Graph Service

- Include Cypher query examples
- Document graph schema changes
- Test query performance

### Recommender Service

- Document algorithm choices
- Include evaluation metrics
- Test recommendation quality

### Orchestrator

- Document API endpoints
- Include request/response examples
- Test inter-service communication

## Pull Request Review Process

1. **Automated Checks**: CI/CD pipeline runs tests
2. **Code Review**: At least one team member reviews
3. **Testing**: Verify functionality works as expected
4. **Documentation**: Ensure docs are updated
5. **Merge**: Once approved, maintainer merges to `develop`

## Communication

- Use GitHub Issues for bug reports and feature requests
- Use PR comments for code-specific discussions
- Use team chat for general questions

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Welcome newcomers

## Questions?

If you have questions, please:

1. Check existing documentation
2. Search closed issues
3. Open a new issue with the "question" label

Thank you for contributing to GraphCeylon-API! 🇱🇰
