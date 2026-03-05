from uuid import uuid4
from ..api.schemas import OrchestrateRequest

def ensure_ids(req: OrchestrateRequest) -> OrchestrateRequest:
    if not req.session_id:
        req.session_id = str(uuid4())
    if not req.trace_id:
        req.trace_id = str(uuid4())
    if not req.turn_id:
        req.turn_id = str(uuid4())
    return req