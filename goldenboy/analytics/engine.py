"""Cost/efficiency/reliability aggregates over the local history log.

Every number here is computed from real `TaskEvent`s (see
`goldenboy.core.history`) already recorded by `budget_aware_execution`.
There is no bundled or synthetic dataset backing any of this: on a fresh
install (zero events), every aggregate is `None` and `AnalyticsReport.render()`
says so explicitly rather than printing a zero or a placeholder that could
be mistaken for a real measurement.
"""
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

from goldenboy.core.history import HistoryStore, TaskEvent

_NA = "N/A — insufficient validated data"


def _mean(values: List[float]) -> Optional[float]:
    return round(statistics.mean(values), 3) if values else None


@dataclass
class AnalyticsReport:
    event_count: int
    mean_cost_percentage: Optional[float]
    mean_cost_by_task_type: Dict[str, float]
    completion_rate: Optional[float]
    failure_rate: Optional[float]
    deferral_rate: Optional[float]
    mean_duration_seconds: Optional[float]
    mode_distribution: Dict[str, int]

    def render(self) -> str:
        lines = [f"Analytics — {self.event_count} recorded event(s)"]
        if self.event_count == 0:
            lines.append(_NA)
            return "\n".join(lines)

        lines.append(
            f"Mean estimated cost:     "
            f"{self.mean_cost_percentage:.2f}%" if self.mean_cost_percentage is not None else _NA
        )
        if self.mean_cost_by_task_type:
            lines.append("Mean estimated cost by task type:")
            for task_type, value in sorted(self.mean_cost_by_task_type.items()):
                lines.append(f"  {task_type}: {value:.2f}%")
        lines.append(
            f"Completion rate:         {self.completion_rate * 100:.1f}%"
            if self.completion_rate is not None
            else _NA
        )
        lines.append(
            f"Deferral rate:           {self.deferral_rate * 100:.1f}%"
            if self.deferral_rate is not None
            else _NA
        )
        lines.append(
            f"Failure rate:            {self.failure_rate * 100:.1f}%"
            if self.failure_rate is not None
            else _NA
        )
        if self.mean_duration_seconds is not None:
            lines.append(f"Mean duration:           {self.mean_duration_seconds:.2f}s")
        if self.mode_distribution:
            lines.append("Risk mode distribution:")
            for mode, count in sorted(self.mode_distribution.items()):
                lines.append(f"  {mode}: {count}")
        return "\n".join(lines)


def _group_mean_cost(events: List[TaskEvent]) -> Dict[str, float]:
    by_type: Dict[str, List[float]] = {}
    for e in events:
        by_type.setdefault(e.task_type, []).append(e.estimated_cost_percentage)
    return {t: round(statistics.mean(v), 3) for t, v in by_type.items()}


def analyze(store: HistoryStore) -> AnalyticsReport:
    result = store.load_events()
    events = result.events
    n = len(events)

    if n == 0:
        return AnalyticsReport(
            event_count=0,
            mean_cost_percentage=None,
            mean_cost_by_task_type={},
            completion_rate=None,
            failure_rate=None,
            deferral_rate=None,
            mean_duration_seconds=None,
            mode_distribution={},
        )

    outcomes = [e.outcome for e in events]
    durations = [e.duration_seconds for e in events if e.duration_seconds is not None]
    mode_distribution: Dict[str, int] = {}
    for e in events:
        mode_distribution[e.decision_mode] = mode_distribution.get(e.decision_mode, 0) + 1

    return AnalyticsReport(
        event_count=n,
        mean_cost_percentage=_mean([e.estimated_cost_percentage for e in events]),
        mean_cost_by_task_type=_group_mean_cost(events),
        completion_rate=outcomes.count("completed") / n,
        failure_rate=outcomes.count("failed") / n,
        deferral_rate=outcomes.count("deferred") / n,
        mean_duration_seconds=_mean(durations),
        mode_distribution=mode_distribution,
    )
