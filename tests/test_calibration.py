from goldenboy.core.calibration import calibrate
from goldenboy.core.telemetry import ExecutionTelemetry


def _telemetry(estimated, actual_tokens, task_type=None, max_budget_tokens=100_000):
    return ExecutionTelemetry.create(
        final_outcome="completed",
        task_type=task_type,
        estimated_cost_percentage=estimated,
        actual_total_tokens=actual_tokens,
        max_budget_tokens=max_budget_tokens,
    )


def test_reports_na_below_minimum_sample_size():
    events = [_telemetry(10.0, 10_000) for _ in range(5)]
    report = calibrate(events)
    assert report.overall.n == 5
    assert report.overall.mae is None
    assert "N/A" in report.overall.render()


def test_perfect_estimates_have_zero_error():
    events = [_telemetry(10.0, 10_000) for _ in range(10)]
    report = calibrate(events)
    assert report.overall.n == 10
    assert report.overall.mae == 0.0
    assert report.overall.bias == 0.0
    assert report.overall.rmse == 0.0


def test_consistent_underestimation_shows_positive_bias():
    # Estimated 10%, actual always 20,000/100,000 = 20% -> error = actual - estimated = +10 each time.
    events = [_telemetry(10.0, 20_000) for _ in range(10)]
    report = calibrate(events)
    assert report.overall.bias == 10.0
    assert report.overall.underestimation_rate == 1.0
    assert report.overall.overestimation_rate == 0.0


def test_consistent_overestimation_shows_negative_bias():
    events = [_telemetry(20.0, 10_000) for _ in range(10)]
    report = calibrate(events)
    assert report.overall.bias == -10.0
    assert report.overall.overestimation_rate == 1.0


def test_records_missing_either_side_are_excluded_not_imputed():
    complete = [_telemetry(10.0, 10_000) for _ in range(10)]
    missing_actual = ExecutionTelemetry.create(final_outcome="completed", estimated_cost_percentage=10.0)
    missing_estimate = ExecutionTelemetry.create(final_outcome="completed", actual_total_tokens=10_000)

    report = calibrate(complete + [missing_actual, missing_estimate])

    assert report.overall.n == 10
    assert report.excluded_missing_data == 2


def test_per_task_type_breakdown_is_isolated_per_category():
    bugfix_events = [_telemetry(10.0, 10_000, task_type="bug_fix") for _ in range(10)]
    arch_events = [_telemetry(10.0, 30_000, task_type="architecture_change") for _ in range(10)]

    report = calibrate(bugfix_events + arch_events)

    assert report.by_task_type["bug_fix"].bias == 0.0
    assert report.by_task_type["architecture_change"].bias == 20.0
    # Aggregate must reflect both categories, not just one.
    assert report.overall.n == 20


def test_empty_events_list_reports_na():
    report = calibrate([])
    assert report.overall.n == 0
    assert report.overall.mae is None


def test_render_includes_metrics_excluded_count_and_per_category_rows():
    complete = [_telemetry(10.0, 10_000, task_type="bug_fix") for _ in range(10)]
    missing_actual = ExecutionTelemetry.create(final_outcome="completed", estimated_cost_percentage=10.0)

    report = calibrate(complete + [missing_actual])
    rendered = report.render()

    assert "MAE=" in rendered
    assert "1 telemetry record(s) excluded" in rendered
    assert "By task type:" in rendered
    assert "bug_fix" in rendered
