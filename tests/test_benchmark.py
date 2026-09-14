from goldenboy.core.benchmark import (
    BenchmarkReport,
    LatencySample,
    benchmark_estimator,
    benchmark_risk_engine,
    run_all,
)


def test_latency_sample_render_includes_label_and_stats():
    sample = LatencySample(label="X", mean_ms=1.0, median_ms=0.9, min_ms=0.5, max_ms=2.0, n=10)
    text = sample.render()
    assert "X" in text
    assert "mean=1.000ms" in text
    assert "n=10" in text


def test_benchmark_estimator_returns_a_positive_latency_sample():
    latency, deterministic, distinct = benchmark_estimator()
    assert latency.n == 20
    assert latency.mean_ms >= 0.0
    assert deterministic is True  # identical prompt -> identical estimate, always
    assert distinct == 1


def test_benchmark_risk_engine_returns_a_sample():
    sample = benchmark_risk_engine()
    assert sample.n == 1000
    assert sample.mean_ms >= 0.0


def test_run_all_produces_a_renderable_report():
    report = run_all()
    assert isinstance(report, BenchmarkReport)
    text = report.render()
    assert "Golden Boy benchmark" in text
    assert report.python_version
    assert report.platform


def test_report_records_errors_instead_of_crashing(monkeypatch):
    import goldenboy.core.benchmark as bench_module

    def _boom():
        raise RuntimeError("no console-script entry point in this environment")

    monkeypatch.setattr(bench_module, "benchmark_cli_startup", _boom)
    report = run_all()

    assert report.cli_startup_latency is None
    assert "cli_startup" in report.errors
    assert "SKIPPED" in report.render()
