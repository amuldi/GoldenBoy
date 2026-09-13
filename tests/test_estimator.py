import os

from goldenboy.core.estimator import Estimator


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_codebase_context_excludes_dependency_directories(tmp_path):
    """A vendored/virtualenv directory sitting next to real source must not
    dominate the context estimate — this is the exact scenario that used
    to send a one-line task's estimate to a clamped 100%."""
    real_src = tmp_path / "src" / "app.py"
    _write(str(real_src), "def hello():\n    return 'hi'\n")

    # Simulate a large vendored dependency tree.
    vendored = tmp_path / "venv" / "lib" / "some_pkg.py"
    _write(str(vendored), "x = 1\n" * 5000)

    node_modules = tmp_path / "node_modules" / "dep" / "index.js"
    _write(str(node_modules), "var x = 1;\n" * 5000)

    estimator = Estimator()
    tokens = estimator._estimate_codebase_context(str(tmp_path))

    # Only the real source file should have been counted; the vendored
    # trees are large enough that any leakage would dominate the total.
    real_only_tokens = estimator._count_tokens(real_src.read_text())
    assert tokens == real_only_tokens


def test_tiny_task_is_not_clamped_to_max_in_a_small_repo(tmp_path, monkeypatch):
    _write(str(tmp_path / "app.py"), "def hello():\n    return 'hi'\n")
    monkeypatch.chdir(tmp_path)

    estimator = Estimator()
    estimate = estimator.estimate_task("Fix a typo in README")

    assert estimate.estimated_percentage < 50.0


def test_estimate_scales_with_prompt_length(tmp_path, monkeypatch):
    """With a repo this small, both prompts would otherwise land under the
    5% floor and look identical -- use a small max_budget_tokens so the
    percentage difference is actually visible above that floor, which is
    the real thing this test is checking (monotonicity in prompt size)."""
    from goldenboy.core.config import GoldenBoyConfig

    _write(str(tmp_path / "app.py"), "def hello():\n    return 'hi'\n")
    monkeypatch.chdir(tmp_path)

    estimator = Estimator(config=GoldenBoyConfig(max_budget_tokens=200))
    small = estimator.estimate_task("Fix a typo")
    large = estimator.estimate_task(
        "Implement a full OAuth login flow with refresh tokens, session "
        "storage, database migrations, and end-to-end tests across the "
        "entire application, including error handling for every provider."
    )

    assert large.estimated_percentage > small.estimated_percentage


def test_fallback_token_counter_distinguishes_equal_word_count_prompts(monkeypatch):
    """Regression test: a pure word-count heuristic (len(text.split()) * k)
    would return the *same* estimate for two prompts with the same word
    count regardless of actual content -- e.g. "Fix a typo in README" and
    "Implement OAuth authentication with tests" are both 5 words. Verified
    live via the actual CLI without tiktoken installed before this was
    fixed. Force the no-tiktoken fallback path here so this stays covered
    even in dev environments where tiktoken is installed."""
    import goldenboy.core.estimator as estimator_module

    monkeypatch.setattr(estimator_module, "HAS_TIKTOKEN", False)
    estimator = estimator_module.Estimator()

    short = estimator._count_tokens("Fix a typo in README")
    long = estimator._count_tokens("Implement OAuth authentication with tests")

    assert short != long


def test_estimate_plan_falls_back_to_config_base_cost():
    from goldenboy.core.config import GoldenBoyConfig
    from goldenboy.core.priorities import ExecutionUnit, Priority

    config = GoldenBoyConfig(base_cost_per_unit=1.5)
    estimator = Estimator(config=config)

    plan = [
        ExecutionUnit("1", "No explicit cost", Priority.P1, estimated_cost=0.0),
        ExecutionUnit("2", "No explicit cost either", Priority.P1, estimated_cost=0.0),
    ]
    estimate = estimator.estimate_plan(plan)

    assert estimate.estimated_percentage == 3.0  # 2 units * 1.5
