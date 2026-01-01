from __future__ import annotations

import httpx
import tempfile
from pathlib import Path


async def download_audio(url: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        Path(tmp.name).write_bytes(r.content)

    return Path(tmp.name)