from typing import Any, Optional

def pref_get(p: Any, key: str, default: Optional[Any] = None) -> Any:
    """
    Uniform preference getter:
    - dict -> .get
    - pydantic/dataclass -> getattr
    """
    if p is None:
        return default
    if isinstance(p, dict):
        return p.get(key, default)
    return getattr(p, key, default)
