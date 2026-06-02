"""Provider-agnostic LLM client with a zero-dependency transport fallback.

The surface is deliberately tiny (``complete_json``), so swapping providers is a
single-file change and callers never import an SDK directly. Two transports are tried in
order:

1. The OpenAI SDK, when installed (richest, supports strict ``json_schema``).
2. A pure-``urllib`` HTTP call to the OpenAI API, so insight still works in locked-down
   environments where no SDK can be installed. It downgrades to ``json_object`` mode, which
   `urllib` and the API support without the SDK's schema plumbing.

Both raise :class:`LLMUnavailable` on any failure so callers fall back to rules.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..config import LLM


class LLMUnavailable(RuntimeError):
    """Raised when no LLM is configured or the request fails."""


def _ssl_context() -> ssl.SSLContext | None:
    """Best-effort CA bundle discovery for environments with no default certs."""

    candidates = (
        os.getenv("SSL_CERT_FILE"),
        "/etc/ssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
    )
    for cert in candidates:
        if cert and Path(cert).exists():
            return ssl.create_default_context(cafile=cert)
    return None


def _complete_via_sdk(
    *, system: str, user: str, schema: dict[str, Any], schema_name: str
) -> dict[str, Any]:
    from openai import OpenAI  # may be absent → ImportError handled by caller

    client = OpenAI(api_key=LLM.api_key)
    resp = client.chat.completions.create(
        model=LLM.model,
        temperature=LLM.temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
    )
    return json.loads(resp.choices[0].message.content or "{}")


def _complete_via_urllib(*, system: str, user: str) -> dict[str, Any]:
    """Pure-stdlib transport: no third-party package required."""

    payload = {
        "model": LLM.model,
        "temperature": LLM.temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {LLM.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise LLMUnavailable("Malformed LLM response")
    return json.loads(content)


def complete_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str = "response",
) -> dict[str, Any]:
    """Return a JSON object from the model. Prefers the SDK, falls back to urllib.

    When using the urllib path (no SDK), the JSON *schema* is appended to the prompt as
    guidance since ``json_object`` mode can't enforce it server-side.
    """

    if LLM.provider != "openai":
        raise LLMUnavailable(f"Unsupported provider: {LLM.provider}")
    if not LLM.is_configured:
        raise LLMUnavailable("OPENAI_API_KEY is not set")

    try:
        return _complete_via_sdk(system=system, user=user, schema=schema, schema_name=schema_name)
    except ImportError:
        pass  # SDK not installed → try stdlib transport
    except Exception as exc:  # noqa: BLE001 - SDK error; try fallback before giving up
        _sdk_error = exc
    else:
        _sdk_error = None

    try:
        guided_system = (
            f"{system}\n\nRespond with a JSON object matching this schema:\n"
            f"{json.dumps(schema)}"
        )
        return _complete_via_urllib(system=guided_system, user=user)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, LLMUnavailable) as exc:
        raise LLMUnavailable(str(_sdk_error or exc)) from exc


def model_label() -> str:
    return f"llm:{LLM.model}"
