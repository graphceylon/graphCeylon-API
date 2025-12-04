# Setup script for GraphCeylon-API development environment
# This script helps set up all services for local development

Write-Host "=== GraphCeylon-API Setup Script ===" -ForegroundColor Green
Write-Host ""

$services = @(
    "language_service",
    "kg_service", 
    "recommender_service",
    "orchestrator"
)

# Function to setup a service
function Setup-Service {
    param (
        [string]$ServiceName
    )
    
    Write-Host "Setting up $ServiceName..." -ForegroundColor Yellow
    
    $servicePath = "services/$ServiceName"
    
    if (Test-Path $servicePath) {
        Push-Location $servicePath
        
        # Create virtual environment with uv
        Write-Host "  Creating virtual environment with uv..." -ForegroundColor Cyan
        uv venv
        
        # Activate virtual environment
        Write-Host "  Activating virtual environment..." -ForegroundColor Cyan
        & ".venv\Scripts\Activate.ps1"
        
        # Install requirements with uv
        Write-Host "  Installing requirements with uv..." -ForegroundColor Cyan
        uv pip install -r requirements.txt --quiet
        
        # Copy env example if .env doesn't exist
        if (-not (Test-Path ".env")) {
            Write-Host "  Creating .env file..." -ForegroundColor Cyan
            Copy-Item ".env.example" ".env"
        }
        
        # Deactivate virtual environment
        deactivate
        
        Pop-Location
        Write-Host "  $ServiceName setup complete!" -ForegroundColor Green
    } else {
        Write-Host "  Error: $servicePath not found!" -ForegroundColor Red
    }
    Write-Host ""
}

# Setup each service
foreach ($service in $services) {
    Setup-Service -ServiceName $service
}

Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Ensure uv is installed: See docs/uv-guide.md"
Write-Host "2. Configure .env files in each service directory"
Write-Host "3. Run with Docker: docker-compose -f infra/docker-compose.yaml up"
Write-Host "4. Or run services individually in their directories"
Write-Host ""
Write-Host "For more information, see docs/getting-started.md" -ForegroundColor Cyan
