import json
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials


def is_firebase_admin_initialized() -> bool:
    return bool(getattr(firebase_admin, "_apps", None))


def init_firebase_admin() -> None:
    """
    Initializes Firebase Admin SDK once.

    Credentials are loaded from either:
    - FIREBASE_SERVICE_ACCOUNT_JSON: JSON string of the service account key
    - GOOGLE_APPLICATION_CREDENTIALS: file path to the service account JSON
    """
    if is_firebase_admin_initialized():
        return

    json_str: Optional[str] = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if json_str and json_str.strip():
        cred = credentials.Certificate(json.loads(json_str))
        firebase_admin.initialize_app(cred)
        return

    # Fallback to standard Google credentials env var / metadata.
    # For local dev, set GOOGLE_APPLICATION_CREDENTIALS to a service account json path.
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        return

    # Last resort: initialize without explicit credentials (may work on some platforms).
    firebase_admin.initialize_app()

