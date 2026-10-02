"""End-to-end tests for the `goldenboy plan-route` CLI command (Stage 4):
previews a real `AdaptiveModelRouter` `RoutingPlan`, distinct from the
existing `goldenboy route` command (old provider-neutral `ModelTier`).
"""
import json

import pytest

from goldenboy.cli import main


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["goldenboy"] + argv)
    main()


def test_plan_route_text_output(monkeypatch, capsys):
    _run(monkeypatch, ["plan-route", "fix a bug in the login flow"])
    out = capsys.readouterr().out
    assert "Golden Boy Adaptive Routing Plan" in out
    assert "Model:" in out
    assert "Token budget:" in out
    assert "Est. cost:" in out
    assert "Reason:" in out


def test_plan_route_json_output_has_expected_shape(monkeypatch, capsys):
    _run(monkeypatch, ["plan-route", "fix a bug in the login flow", "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["provider"] is not None
    assert data["model"] is not None
    assert "input_budget_tokens" in data
    assert "output_budget_tokens" in data
    assert "estimated_cost" in data
    assert "fallback_chain" in data
    assert "reasoning" in data


def test_plan_route_json_never_prints_secrets(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-totally-secret-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-totally-secret-value")
    _run(monkeypatch, ["plan-route", "fix a bug", "--json"])
    out = capsys.readouterr().out
    assert "sk-ant-totally-secret-value" not in out
    assert "sk-openai-totally-secret-value" not in out


def test_plan_route_respects_strategy_override(monkeypatch, capsys):
    _run(monkeypatch, ["plan-route", "fix a bug", "--strategy", "quality_first"])
    out = capsys.readouterr().out
    assert "Strategy:     quality_first" in out


def test_plan_route_respects_min_quality(monkeypatch, capsys):
    _run(monkeypatch, [
        "plan-route", "fix a bug", "--min-quality", "frontier", "--json",
    ])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["model"] in ("claude-opus-4-1",)


def test_plan_route_rejects_blank_task(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        _run(monkeypatch, ["plan-route", "   "])
    err = capsys.readouterr().err
    assert err.strip() != ""


def test_plan_route_quiet_suppresses_banner(monkeypatch, capsys):
    _run(monkeypatch, ["plan-route", "fix a bug", "--quiet"])
    out = capsys.readouterr().out
    assert "Golden Boy Adaptive Routing Plan" not in out
    assert "Model:" in out


def test_plan_route_is_read_only_no_audit_or_spending_side_effects(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["plan-route", "fix a bug"])
    capsys.readouterr()
    assert not (tmp_path / ".goldenboy" / "audit.jsonl").exists()
    assert not (tmp_path / ".goldenboy" / "spending.jsonl").exists()
