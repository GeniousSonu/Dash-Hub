import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any
from fastapi import HTTPException, status

from backend.app.core.config import settings

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "system_admin": {
        "manage_users",
        "manage_templates",
        "manage_integrations",
        "assign_work",
        "execute_maintenance",
        "approve_developer_changes",
        "approve_manager_exceptions",
        "verify_work",
        "view_records",
        "export_reports",
    },
    "manager": {
        "assign_work",
        "execute_maintenance",
        "approve_manager_exceptions",
        "verify_work",
        "view_records",
        "export_reports",
    },
    "Dev_Ops_Engineer": {
        "assign_work",
        "execute_maintenance",
        "approve_manager_exceptions",
        "verify_work",
        "view_records",
        "export_reports",
    },
    "maintenance_engineer": {
        "execute_maintenance",
        "view_records",
        "export_reports",
    },
    "developer": {
        "execute_maintenance",
        "approve_developer_changes",
        "view_records",
        "export_reports",
    },
    "reviewer_qa": {
        "verify_work",
        "view_records",
        "export_reports",
    },
    "readonly_stakeholder": {
        "view_records",
    },
    "report_recipient": set(),
}


def check_permission(user_row: dict[str, Any] | None, required_permission: str) -> None:
    if not user_row or not user_row.get("is_active", 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or unrecognized.",
        )
    role = user_row.get("role", "")
    perms = ROLE_PERMISSIONS.get(role, set())
    if required_permission not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' does not have permission '{required_permission}'.",
        )


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload["exp"] = expire.timestamp()
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload, default=str).encode()).decode()
    signature = hmac.new(
        settings.jwt_secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"opshub.{encoded_payload}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "opshub":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token format.",
        )
    encoded_payload, sig = parts[1], parts[2]
    expected_sig = hmac.new(
        settings.jwt_secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature.",
        )
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded_payload.encode()).decode())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )
    exp = payload.get("exp")
    if exp and datetime.now(timezone.utc).timestamp() > exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
        )
    return payload
