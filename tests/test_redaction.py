from goldenboy.core.redaction import redact_secrets


def test_empty_and_none_pass_through():
    assert redact_secrets("") == ""
    assert redact_secrets(None) is None


def test_plain_text_unchanged():
    text = "the build failed because the test suite timed out"
    assert redact_secrets(text) == text


def test_openai_style_key_redacted():
    redacted = redact_secrets("using key sk-abcdefghijklmnopqrstuvwx now")
    assert "sk-abcdefghijklmnopqrstuvwx" not in redacted
    assert "[REDACTED]" in redacted


def test_password_assignment_redacted():
    redacted = redact_secrets("password: hunter2isastrongone")
    assert "hunter2isastrongone" not in redacted
