"""Load approved runtime secrets from AWS Secrets Manager through IAM.

The secret identifier is configuration, not a credential. Secret values are
kept out of Terraform state, deployment output, command arguments, and files.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from typing import Any

SECRET_KEYS = ("GROQ_API_KEY", "GROQ_MODEL", "ATLAS_ACCESS_TOKEN")
_lock = threading.Lock()
_loaded_secret_id: str | None = None


def _boto3():
    import boto3
    return boto3


def _secret_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("SecretString"), str):
        return response["SecretString"]
    binary = response.get("SecretBinary")
    if isinstance(binary, str):
        return base64.b64decode(binary).decode("utf-8")
    if isinstance(binary, bytes):
        return binary.decode("utf-8")
    raise RuntimeError("Atlas runtime secret has no readable value")


def load_runtime_secrets() -> bool:
    """Load the configured secret once; return False in explicit local mode."""
    global _loaded_secret_id
    secret_id = os.getenv("ATLAS_RUNTIME_SECRET_ID", "").strip()
    if not secret_id:
        return False
    with _lock:
        if _loaded_secret_id == secret_id:
            return True
        response = _boto3().client(
            "secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1")
        ).get_secret_value(SecretId=secret_id)
        payload = json.loads(_secret_text(response))
        if not isinstance(payload, dict):
            raise RuntimeError("Atlas runtime secret must be a JSON object")
        for key in SECRET_KEYS:
            value = payload.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                raise RuntimeError(f"Atlas runtime secret field {key} must be a string")
            if value and not os.getenv(key):
                os.environ[key] = value
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("Atlas runtime secret is missing GROQ_API_KEY")
        _loaded_secret_id = secret_id
        return True
