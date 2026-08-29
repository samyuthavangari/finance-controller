from pathlib import Path

from fastapi import Header, HTTPException

from app.config.policy import policy
from app.config.settings import settings


def require_auth(authorization: str | None = Header(default=None)) -> str:
    if not settings.auth_enabled:
        return "anonymous"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.api_auth_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def validate_upload(filename: str, content_type: str | None, size: int) -> None:
    if size > policy.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    ext = Path(filename).suffix.lower()
    if ext not in policy.allowed_ext:
        raise HTTPException(status_code=400, detail=f"Extension not allowed: {ext}")
    name = Path(filename).name
    if ".." in filename.replace("\\", "/") or name != Path(filename).name:
        raise HTTPException(status_code=400, detail="Invalid path")
    if content_type and content_type.split(";")[0].strip() not in policy.allowed_mime:
        # CSV uploads often omit MIME; still allow known extensions
        if ext not in {".csv", ".json", ".txt"}:
            raise HTTPException(status_code=400, detail=f"MIME not allowed: {content_type}")
