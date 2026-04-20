#!/bin/bash
# Start FastAPI server in background
python -m uvicorn src.main:app --host 0.0.0.0 --port 8002 &
# Start MCP server (adjust path/module as needed)
python -m uvicorn src.orchestrator_core.servers.mcp_server_http:fastapi_app --host 0.0.0.0 --port 9101 &
# Wait for background jobs
wait
