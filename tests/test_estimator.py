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


def test_relevant_context_is_zero_when_task_matches_no_file_path(tmp_path, monkeypatch):
    """Regression test for the P0 finding in ARCHITECTURE_AUDIT.md: a task
    whose wording matches nothing in the repo must not silently fall back
    to scanning everything -- it should report zero relevant context, not
    a repo-sized number."""
    _write(str(tmp_path / "src" / "unrelated_module.py"), "def handler():\n    return 1\n")
    monkeypatch.chdir(tmp_path)

    estimator = Estimator()
    tokens, count = estimator._estimate_relevant_context("Fix a typo in the login page")

    assert tokens == 0
    assert count == 0


def test_relevant_context_matches_files_by_keyword_in_path(tmp_path, monkeypatch):
    _write(str(tmp_path / "auth" / "login.py"), "def login():\n    return True\n" * 5)
    _write(str(tmp_path / "billing" / "invoice.py"), "def invoice():\n    return True\n" * 500)
    monkeypatch.chdir(tmp_path)

    estimator = Estimator()
    tokens, count = estimator._estimate_relevant_context("Fix a bug in the login flow")

    # Only auth/login.py should match "login" -- billing/invoice.py (much
    # larger) must not be pulled in just because it also exists in the repo.
    assert count == 1
    login_tokens = estimator._count_tokens((tmp_path / "auth" / "login.py").read_text())
    assert tokens == login_tokens


def test_two_tasks_in_the_same_repo_get_different_estimates(tmp_path, monkeypatch):
    """The exact regression this upgrade targets: before the fix, a tiny
    task and a large architectural task in the same (non-trivial) repo
    landed on the same estimated_percentage because repo size dominated
    the formula. They must now differ. A small `max_budget_tokens` (as in
    `test_estimate_scales_with_prompt_length`) keeps both estimates above
    the 5% floor so the difference is actually visible."""
    from goldenboy.core.config import GoldenBoyConfig

    for i in range(30):
        _write(str(tmp_path / "pkg" / f"module_{i}.py"), "x = 1\n" * 200)
    monkeypatch.chdir(tmp_path)

    estimator = Estimator(config=GoldenBoyConfig(max_budget_tokens=200))
    small = estimator.estimate_task("Fix a typo in the help text")
    large = estimator.estimate_task(
        "Re-architect the data model and migrate the storage layer to the new "
        "schema across all modules, with full test coverage"
    )

    assert small.estimated_percentage != large.estimated_percentage
    assert large.complexity_score > small.complexity_score


def test_confidence_is_lower_when_no_relevant_files_are_found(tmp_path, monkeypatch):
    import goldenboy.core.estimator as estimator_module

    _write(str(tmp_path / "app.py"), "x = 1\n")
    monkeypatch.chdir(tmp_path)

    estimator = Estimator()
    estimate = estimator.estimate_task("Fix a typo nowhere near any real file")
    full_confidence = 0.85 if estimator_module.HAS_TIKTOKEN else 0.50

    assert estimate.relevant_file_count == 0
    assert estimate.confidence < full_confidence


def test_repository_tokens_is_still_reported_separately_from_relevant_context(tmp_path, monkeypatch):
    """`repository_tokens` (whole-repo size) must still be computed and
    exposed for transparency, even though it no longer feeds the cost
    total directly."""
    _write(str(tmp_path / "auth" / "login.py"), "def login():\n    return True\n")
    _write(str(tmp_path / "unrelated.py"), "x = 1\n" * 100)
    monkeypatch.chdir(tmp_path)

    estimator = Estimator()
    estimate = estimator.estimate_task("Fix the login flow")

    assert estimate.repository_tokens > estimate.relevant_context_tokens
    assert estimate.relevant_context_tokens > 0


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
