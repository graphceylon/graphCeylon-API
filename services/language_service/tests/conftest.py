"""
pytest configuration for Language Service tests.

Sets environment variables BEFORE any src.* import so that config.py never
tries to open the real GCP credentials file or connect to live services.
"""

import os
import sys

# ── Stub GCP credentials so config.py does not touch the file-system ─────────
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/test-creds.json")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("ORCHESTRATOR_URL", "http://mock-orchestrator:8002")
os.environ.setdefault("MOCK_ORCHESTRATOR", "false")

import pytest


@pytest.fixture(autouse=True)
def reset_module_singletons():
    """
    Reset the lazy GCP client singletons in each service module before every
    test so patches from one test cannot bleed into another.
    """
    yield
    for mod_name in ("src.stt", "src.tts", "src.translation"):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "_client"):
            mod._client = None
