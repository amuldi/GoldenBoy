"""Data-quality validation for the local history log.

Runs entirely against whatever `HistoryStore` actually contains -- on a
fresh install that's zero rows, and the report says so (`NO_DATA`) rather
than reporting a fabricated baseline. Every count here is a real
measurement over real (possibly empty) local data; nothing is sampled from
an external dataset.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from goldenboy.core.history import HistoryStore, TaskEvent

# Fixed, documented status thresholds -- a chosen policy, not a trained
# cutoff. `invalid_ratio` = (corrupted lines + rows that parsed but failed
# a value-sanity check) / total_lines.
_GOOD_MAX_INVALID_RATIO = 0.01
_ACCEPTABLE_MAX_INVALID_RATIO = 0.05

_PERCENTAGE_FIELDS = (
    "estimated_cost_percentage", "remaining_usage_start", "remaining_usage_end",
)
_UNIT_INTERVAL_FIELDS = ("task_type_confidence", "estimated_cost_confidence")


def _value_errors(event: TaskEvent) -> List[str]:
    """Sanity checks beyond "did it parse" -- impossible values that a
    schema check alone wouldn't catch."""
    errors = []
    for name in _PERCENTAGE_FIELDS:
        value = getattr(event, name)
        if value is not None and not (0.0 <= value <= 100.0):
            errors.append(f"{name}={value!r} outside [0, 100]")
    for name in _UNIT_INTERVAL_FIELDS:
        value = getattr(event, name)
        if not (0.0 <= value <= 1.0):
            errors.append(f"{name}={value!r} outside [0, 1]")
    if event.duration_seconds is not None and event.duration_seconds < 0:
        errors.append(f"duration_seconds={event.duration_seconds!r} is negative")
    try:
        datetime.fromisoformat(event.timestamp)
    except (ValueError, TypeError):
        errors.append(f"timestamp={event.timestamp!r} is not valid ISO 8601")
    return errors


@dataclass
class DataQualityReport:
    total_lines: int
    valid_rows: int
    corrupted_rows: int
    invalid_value_rows: int
    duplicate_rows: int
    status: str
    issues: Dict[str, int] = field(default_factory=dict)

    @property
    def missing_ratio(self) -> float:
        return (self.corrupted_rows / self.total_lines) if self.total_lines else 0.0

    @property
    def duplicate_ratio(self) -> float:
        return (self.duplicate_rows / self.total_lines) if self.total_lines else 0.0

    @property
    def invalid_ratio(self) -> float:
        return (
            (self.corrupted_rows + self.invalid_value_rows) / self.total_lines
            if self.total_lines
            else 0.0
        )

    def render(self) -> str:
        if self.total_lines == 0:
            return (
                "Dataset Quality\n"
                "Rows:                 0\n"
                "Status: NO_DATA — insufficient validated data (no history recorded yet)."
            )
        lines = [
            "Dataset Quality",
            f"Rows:              {self.total_lines}",
            f"Valid:             {self.valid_rows}",
            f"Corrupted:            {self.missing_ratio * 100:.1f}%",
            f"Duplicates:           {self.duplicate_ratio * 100:.1f}%",
            f"Invalid records:      {self.invalid_ratio * 100:.1f}%",
            f"Status: {self.status}",
        ]
        if self.issues:
            lines.append("Issue breakdown:")
            for name, count in sorted(self.issues.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {name}: {count}")
        return "\n".join(lines)


def validate(store: HistoryStore) -> DataQualityReport:
    result = store.load_events()

    seen_keys = set()
    duplicate_rows = 0
    invalid_value_rows = 0
    issues: Dict[str, int] = {}

    for event in result.events:
        key = (event.prompt_hash, event.timestamp, event.outcome)
        if key in seen_keys:
            duplicate_rows += 1
        else:
            seen_keys.add(key)

        errors = _value_errors(event)
        if errors:
            invalid_value_rows += 1
            for e in errors:
                field_name = e.split("=", 1)[0]
                issues[field_name] = issues.get(field_name, 0) + 1

    total_lines = result.total_lines
    if total_lines == 0:
        status = "NO_DATA"
    else:
        invalid_ratio = (result.corrupted_lines + invalid_value_rows) / total_lines
        if invalid_ratio <= _GOOD_MAX_INVALID_RATIO:
            status = "GOOD"
        elif invalid_ratio <= _ACCEPTABLE_MAX_INVALID_RATIO:
            status = "ACCEPTABLE"
        else:
            status = "POOR"

    return DataQualityReport(
        total_lines=total_lines,
        valid_rows=len(result.events) - invalid_value_rows,
        corrupted_rows=result.corrupted_lines,
        invalid_value_rows=invalid_value_rows,
        duplicate_rows=duplicate_rows,
        status=status,
        issues=issues,
    )
