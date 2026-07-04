import hashlib
import hmac
import time
from typing import Any

import jwt
import requests

from nyuydine.config import get_platform_settings
from utils.logging import get_logger

logger = get_logger("github_app")

GITHUB_API = "https://api.github.com"


def _load_private_key() -> str:
    settings = get_platform_settings()
    key = settings.resolve_github_private_key()
    if not key:
        raise RuntimeError("GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH is required")
    return key


def create_app_jwt() -> str:
    settings = get_platform_settings()
    if not settings.github_app_id:
        raise RuntimeError("GITHUB_APP_ID is required")

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, _load_private_key(), algorithm="RS256")


def get_installation_token(installation_id: int) -> str:
    app_jwt = create_app_jwt()
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("token")
    if not token:
        raise RuntimeError(f"No token in installation response: {payload}")
    return str(token)


def verify_webhook_signature(body: bytes, signature_header: str | None) -> bool:
    settings = get_platform_settings()
    secret = settings.github_webhook_secret
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — rejecting webhook")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def parse_repository(payload: dict[str, Any]) -> tuple[str, str, str]:
    repo = payload.get("repository") or {}
    owner = (repo.get("owner") or {}).get("login", "")
    name = repo.get("name", "")
    full_name = repo.get("full_name") or f"{owner}/{name}"
    return owner, name, full_name
