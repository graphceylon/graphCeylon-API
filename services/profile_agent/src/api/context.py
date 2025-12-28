from fastapi import APIRouter
from pydantic import BaseModel
from ..core.context_builder import ProfileContextBuilder

router = APIRouter()
builder = ProfileContextBuilder()

class ContextRequest(BaseModel):
    user_id: str
    session_id: str
    db_prefs: dict
    query_overrides: dict
    raw_text: str

@router.post("/profile/context")
def build_profile_context(req: ContextRequest):
    return builder.build_context(req.db_prefs, req.query_overrides)
