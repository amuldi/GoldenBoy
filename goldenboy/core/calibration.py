"""Estimation calibration: how close was `Estimator`'s
`estimated_cost_percentage` to what actually happened, per
`goldenboy.core.telemetry.ExecutionTelemetry`?

This is the evaluation half of the feedback loop `goldenboy.core.telemetry`
makes possible: estimate -> execute -> observe (telemetry) -> **compare**
(this module) -> improve. It only ever operates on real, reported
`ExecutionTelemetry` records -- there is no bundled or synthetic dataset,
and a record missing either side of the comparison (`estimated_cost_
percentage` or `actual_cost_percentage`) is excluded from that comparison
rather than imputed.

Below `_MIN_SAMPLES_FOR_METRICS` usable pairs, every metric is reported as
`None` -- the same "N/A below a floor" convention `goldenboy.replay` already
uses for backtesting, for the same reason: a MAE computed over two or three
points implies far more statistical weight than it has.

Metrics reported (see the project brief, section 9):
    - MAE, RMSE, median absolute error: overall estimate-quality.
    - Bias (mean(actual - estimated)): positive means Golden Boy under-
      estimates on average; negative means it overestimates on average.
    - Overestimation / underestimation rate: fraction of pairs on each
      side of zero error. Reported *in addition to* the aggregate error
      metrics -- an estimator that is accurate on easy tasks but
      consistently underestimates hard ones is dangerous in a way MAE
      alone hides (see the project brief's explicit warning on this).
    - The same four metrics broken out per `task_type`, when that field
      was echoed on the telemetry record -- again, N/A per-category below
      the sample floor for that category specifically.
"""
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from goldenboy.core.telemetry import ExecutionTelemetry

# Below this many usable (estimated, actual) pairs, every metric for that
# slice (aggregate or per-category) is None -- not a computed number.
_MIN_SAMPLES_FOR_METRICS = 10


@dataclass
class ErrorPair:
    estimated: float
    actual: float

    @property
    def error(self) -> float:
        """actual - estimated: positive means Golden Boy underestimated."""
        return self.actual - self.estimated


@dataclass
class CalibrationMetrics:
    n: int
    mae: Optional[float]
    rmse: Optional[float]
    median_absolute_error: Optional[float]
    bias: Optional[float]  # mean(actual - estimated); >0 = underestimates on average
    overestimation_rate: Optional[float]  # fraction of pairs where estimated > actual
    underestimation_rate: Optional[float]  # fraction of pairs where estimated < actual

    def render(self) -> str:
        if self.n < _MIN_SAMPLES_FOR_METRICS:
            return f"n={self.n} (need >= {_MIN_SAMPLES_FOR_METRICS}) -- N/A, insufficient data"

        def pct(v: Optional[float]) -> str:
            return f"{v * 100:.1f}%" if v is not None else "N/A"

        return (
            f"n={self.n}  MAE={self.mae:.2f}pp  RMSE={self.rmse:.2f}pp  "
            f"median_abs_err={self.median_absolute_error:.2f}pp  bias={self.bias:+.2f}pp  "
            f"overestimated={pct(self.overestimation_rate)}  underestimated={pct(self.underestimation_rate)}"
        )


@dataclass
class CalibrationReport:
    overall: CalibrationMetrics
    by_task_type: Dict[str, CalibrationMetrics] = field(default_factory=dict)
    excluded_missing_data: int = 0  # telemetry records with no usable (estimated, actual) pair

    def render(self) -> str:
        lines = [f"Calibration (estimated vs. actual cost percentage): {self.overall.render()}"]
        if self.excluded_missing_data:
            lines.append(
                f"  ({self.excluded_missing_data} telemetry record(s) excluded: missing "
                "estimated_cost_percentage or actual_cost_percentage)"
            )
        if self.by_task_type:
            lines.append("By task type:")
            for task_type in sorted(self.by_task_type):
                lines.append(f"  {task_type:<24} {self.by_task_type[task_type].render()}")
        return "\n".join(lines)


def _extract_pairs(events: List[ExecutionTelemetry]) -> List[ErrorPair]:
    pairs = []
    for event in events:
        if event.estimated_cost_percentage is not None and event.actual_cost_percentage is not None:
            pairs.append(ErrorPair(event.estimated_cost_percentage, event.actual_cost_percentage))
    return pairs


def _compute_metrics(pairs: List[ErrorPair]) -> CalibrationMetrics:
    n = len(pairs)
    if n < _MIN_SAMPLES_FOR_METRICS:
        return CalibrationMetrics(
            n=n, mae=None, rmse=None, median_absolute_error=None,
            bias=None, overestimation_rate=None, underestimation_rate=None,
        )

    errors = [p.error for p in pairs]
    abs_errors = [abs(e) for e in errors]
    overestimated = sum(1 for e in errors if e < 0)
    underestimated = sum(1 for e in errors if e > 0)

    return CalibrationMetrics(
        n=n,
        mae=statistics.mean(abs_errors),
        rmse=math.sqrt(statistics.mean(e * e for e in errors)),
        median_absolute_error=statistics.median(abs_errors),
        bias=statistics.mean(errors),
        overestimation_rate=overestimated / n,
        underestimation_rate=underestimated / n,
    )


def calibrate(events: List[ExecutionTelemetry]) -> CalibrationReport:
    """Computes overall and per-task-type calibration metrics from real
    `ExecutionTelemetry` records. Records missing either side of the
    (estimated, actual) pair are counted in `excluded_missing_data` and
    left out of every metric, never imputed."""
    usable = [e for e in events if e.estimated_cost_percentage is not None
              and e.actual_cost_percentage is not None]
    excluded = len(events) - len(usable)

    overall = _compute_metrics(_extract_pairs(usable))

    by_type: Dict[str, List[ExecutionTelemetry]] = defaultdict(list)
    for event in usable:
        if event.task_type:
            by_type[event.task_type].append(event)

    by_task_type = {
        task_type: _compute_metrics(_extract_pairs(type_events))
        for task_type, type_events in by_type.items()
    }

    return CalibrationReport(overall=overall, by_task_type=by_task_type, excluded_missing_data=excluded)
