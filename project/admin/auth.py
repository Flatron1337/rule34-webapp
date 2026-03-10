from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar, Any

from flask import request, jsonify
from firebase_admin import auth
from google.auth.exceptions import DefaultCredentialsError

from .firebase_admin import is_firebase_admin_initialized


T = TypeVar("T")


def _get_bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].strip(), parts[1].strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_admin(fn: Callable[..., T]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # If admin routes are somehow reachable without Firebase initialized,
        # return a clear error instead of masking it as "invalid_token".
        if not is_firebase_admin_initialized():
            return jsonify({"error": "firebase_not_initialized"}), 503

        token = _get_bearer_token()
        if not token:
            return jsonify({"error": "missing_authorization"}), 401

        try:
            decoded = auth.verify_id_token(token, check_revoked=True)
        except Exception as e:
            # Common case when Firebase Admin SDK wasn't initialized properly.
            msg = str(e)
            if isinstance(e, DefaultCredentialsError):
                return jsonify({"error": "firebase_credentials_missing"}), 503
            if isinstance(e, ValueError) or "default Firebase app does not exist" in msg:
                return jsonify({"error": "firebase_not_initialized"}), 503
            # Keep auth failures as 401, but don't hide init/config issues.
            return jsonify({"error": "invalid_token"}), 401

        claims = decoded or {}
        if claims.get("admin") is not True:
            return jsonify({"error": "forbidden"}), 403

        return fn(*args, **kwargs)

    return wrapper

