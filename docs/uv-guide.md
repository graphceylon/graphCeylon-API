# UV Package Manager

This project uses [uv](https://github.com/astral-sh/uv) as the package manager for faster and more reliable Python dependency management.

## Why UV?

- **Fast**: 10-100x faster than pip
- **Reliable**: Better dependency resolution
- **Modern**: Built with Rust for performance
- **Compatible**: Works with standard requirements.txt files

## Installation

### Windows (PowerShell)

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Linux/macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Usage

### Create Virtual Environment

```bash
uv venv
```

This creates a `.venv` directory in your project.

### Activate Virtual Environment

**Windows:**

```powershell
.venv\Scripts\activate
```

**Linux/macOS:**

```bash
source .venv/bin/activate
```

### Install Dependencies

```bash
uv pip install -r requirements.txt
```

### Install Individual Packages

```bash
uv pip install package-name
```

### Add to requirements.txt

```bash
uv pip install package-name
uv pip freeze > requirements.txt
```

## Quick Start for Team Members

1. **Install uv** (one-time setup):

   ```powershell
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Set up a service**:

   ```bash
   cd services/language_service
   uv venv
   .venv\Scripts\activate  # Windows
   uv pip install -r requirements.txt
   ```

3. **Run the service**:
   ```bash
   python src/main.py
   ```

## Docker

All Dockerfiles are configured to use uv automatically. No additional setup needed for Docker deployments.

## CI/CD

GitHub Actions workflows are configured to use uv for faster builds and tests.

## Resources

- [UV Documentation](https://github.com/astral-sh/uv)
- [UV Installation Guide](https://github.com/astral-sh/uv#installation)
