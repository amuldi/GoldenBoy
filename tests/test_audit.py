import os

import pytest

from goldenboy.core.audit import AuditEntry, AuditStore


def test_create_validates_result():
    with pytest.raises(ValueError):
        AuditEntry.create(action="scan", result="not_a_real_result")


def test_create_validates_nonempty_action():
    with pytest.raises(ValueError):
        AuditEntry.create(action="", result="success")


def test_store_append_and_load(tmp_path):
    store = AuditStore(history_dir=str(tmp_path))
    store.record(AuditEntry.create(action="scan", result="success", estimated_cost=18000, actual_cost=16421))

    result = store.load_events()
    assert len(result.events) == 1
    entry = result.events[0]
    assert entry.action == "scan"
    assert entry.estimated_cost == 18000
    assert entry.actual_cost == 16421


def test_store_tolerates_corrupted_lines(tmp_path):
    store = AuditStore(history_dir=str(tmp_path))
    store.record(AuditEntry.create(action="scan", result="success"))
    with open(store.audit_file, "a", encoding="utf-8") as f:
        f.write("not even json\n")

    result = store.load_events()
    assert len(result.events) == 1
    assert result.corrupted_lines == 1


def test_missing_file_returns_empty(tmp_path):
    store = AuditStore(history_dir=str(tmp_path / "nope"))
    result = store.load_events()
    assert result.events == []
    assert result.total_lines == 0


def test_clear_removes_file(tmp_path):
    store = AuditStore(history_dir=str(tmp_path))
    store.record(AuditEntry.create(action="scan", result="success"))
    assert os.path.exists(store.audit_file)
    store.clear()
    assert not os.path.exists(store.audit_file)


# --- Secret redaction ----------------------------------------------------


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ant-api03-abcdefghij1234567890",
        "sk-abcdefghijklmnopqrstuvwx",
        "ghp_abcdefghijklmnopqrstuvwxyz012345",
        "AKIAABCDEFGHIJKLMNOP",
        "Bearer abcdef1234567890.xyz",
        "api_key=abcdef1234567890",
    ],
)
def test_error_field_redacts_known_secret_shapes(secret):
    entry = AuditEntry.create(action="scan", result="failure", error=f"request failed, token was {secret}")
    assert secret not in entry.error
    assert "[REDACTED]" in entry.error


def test_extra_string_fields_are_also_redacted():
    entry = AuditEntry.create(
        action="scan", result="failure", extra={"detail": "used key sk-ant-api03-abcdefghij1234567890"}
    )
    assert "sk-ant-api03" not in entry.extra["detail"]


def test_extra_nonstring_values_pass_through_unchanged():
    entry = AuditEntry.create(action="scan", result="success", extra={"count": 42, "ok": True})
    assert entry.extra == {"count": 42, "ok": True}


def test_redaction_survives_persist_and_reload(tmp_path):
    store = AuditStore(history_dir=str(tmp_path))
    store.record(
        AuditEntry.create(action="scan", result="failure", error="key=sk-ant-api03-abcdefghij1234567890")
    )

    raw = (tmp_path / "audit.jsonl").read_text()
    assert "sk-ant-api03-abcdefghij1234567890" not in raw

    reloaded = store.load_events().events[0]
    assert "sk-ant-api03" not in reloaded.error


def test_render_includes_key_fields():
    entry = AuditEntry.create(
        action="scan", result="success", tool="bash", decision="allow", policy_result="ALLOWED",
        estimated_cost=18000, actual_cost=16421,
    )
    rendered = entry.render()
    assert "ACTION: scan" in rendered
    assert "TOOL: bash" in rendered
    assert "RESULT: success" in rendered
    assert "18,000 tokens" in rendered
    assert "16,421 tokens" in rendered
