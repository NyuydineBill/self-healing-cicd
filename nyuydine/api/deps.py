import json

from fastapi import Depends, Header, HTTPException, status

from nyuydine.config import get_platform_settings
from nyuydine.db.session import get_db


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_platform_settings()
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


DbSession = Depends(get_db)
ApiAuth = Depends(require_api_key)


def parse_result_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
