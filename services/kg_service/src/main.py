"""Main application entry point for Knowledge Graph Service."""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.absolute()
sys.path.insert(0, str(src_path))

# Set working directory to src
os.chdir(src_path)

# Import the fully configured app from api.main
from api.main import app

if __name__ == "__main__":
    import uvicorn
    from core.config import settings
    
    print(f"Starting Knowledge Graph Service...")
    print(f"API Host: {settings.api_host}")
    print(f"API Port: {settings.api_port}")
    print(f"Debug Mode: {settings.debug}")
    print(f"Neo4j URI: {settings.neo4j_uri}")
    
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info"
    )
    
    
    
    
