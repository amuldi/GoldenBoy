"""Shared secret-redaction helper, used by `goldenboy.core.audit` and
`goldenboy.core.failure_memory` before either writes free-text (an error
message, a failure cause) to disk.

This is a defensive second layer, not the primary safeguard -- the primary
safeguard, as in the rest of Golden Boy (see SECURITY.md), is never passing
a secret into these fields in the first place. But `error`/`cause_summary`
strings originate from whatever the caller passes (e.g. a subprocess's
stderr, or an agent's own exception text), which Golden Boy does not
control the contents of -- so anything that looks like a credential is
masked before it ever reaches a persisted `.goldenboy/*.jsonl`/`.json` file.

Pattern-based, not a secrets-scanning service: it catches common,
recognizable shapes (API-key-like tokens, bearer tokens, explicit
`key=value`/`key: value` assignments naming a credential) and nothing more.
"""
import re
from typing import Pattern, Tuple

# (label, compiled pattern) -- label is only used in tests/debugging, never
# written to output. Ordered roughly from most to least specific so a more
# specific match (e.g. a well-known provider prefix) isn't shadowed by a
# broader one.
_SECRET_PATTERNS: Tuple[Tuple[str, Pattern], ...] = (
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{10,}")),
    (
        "assigned_credential",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|access[_-]?key)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9/+_.-]{6,}['\"]?"
        ),
    ),
)

_REDACTED = "[REDACTED]"


def redact_secrets(text: str) -> str:
    """Return `text` with anything matching a known secret shape replaced by
    `[REDACTED]`. Safe to call on text with nothing to redact (returned
    unchanged) or on `None`-ish falsy input (returned as-is)."""
    if not text:
        return text
    redacted = text
    for _label, pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted
