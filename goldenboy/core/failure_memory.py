"""Failure Memory: a minimal record of *why* past tasks failed, so a future
task can check "has this happened before" instead of repeating a known
mistake blind.

Deliberately simple, per the project brief: no vector database, no
embeddings. Matching is done two ways, both cheap and local:

    1. Exact match -- a normalized, hashed signature of the failure cause
       (numbers/paths blanked out so "line 42 failed" and "line 57 failed"
       hash the same; see `_normalize_cause`). Repeating exactly the same
       kind of failure increments `attempt_count` on the same record.
    2. Fuzzy match (`find_similar`) -- keyword-overlap (Jaccard similarity
       over a simple word set, no ML) against every stored record's cause
       text, for "related but not identical" failures.

State is a single mutable JSON document (`.goldenboy/failures.json`, same
convention as `CheckpointManager`), keyed by signature -- not an
append-only log, since the point is *one row per distinct failure cause*
that accumulates an attempt count and an optional resolution, not a full
history of every attempt.

Same secret-redaction pass as `goldenboy.core.audit` (see
`goldenboy.core.redaction`) is applied to `cause_summary`/`resolution`
before anything is written to disk.
"""
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.redaction import redact_secrets

FAILURE_MEMORY_SCHEMA_VERSION = 1

_DIGIT_RUN = re.compile(r"\d+")
_WHITESPACE_RUN = re.compile(r"\s+")
_WORD_PATTERN = re.compile(r"[a-z][a-z0-9_-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
    "had", "was", "with", "from", "this", "that", "error", "failed",
    "failure", "line", "file", "test",
}


class FailureMemoryError(GoldenBoyError):
    """The failure-memory file exists but is corrupted or malformed."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_cause(text: str) -> str:
    """Lowercased, whitespace-collapsed, with digit runs blanked to `#` --
    so two failures that differ only by a line number, a count, or a
    timestamp still normalize (and therefore hash) the same."""
    lowered = text.strip().lower()
    lowered = _DIGIT_RUN.sub("#", lowered)
    lowered = _WHITESPACE_RUN.sub(" ", lowered)
    return lowered


def _signature(text: str) -> str:
    import hashlib

    return hashlib.sha256(_normalize_cause(text).encode("utf-8", errors="replace")).hexdigest()[:16]


def _keywords(text: str) -> set:
    return {w for w in _WORD_PATTERN.findall(text.lower()) if w not in _STOPWORDS}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


@dataclass
class FailureRecord:
    schema_version: int
    signature: str
    cause_summary: str
    task_type: Optional[str]
    attempt_count: int
    first_seen: str
    last_seen: str
    resolution: Optional[str] = None
    resolved: bool = False
    extra: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "FailureRecord":
        return cls(
            schema_version=data["schema_version"],  # type: ignore[arg-type]
            signature=data["signature"],  # type: ignore[arg-type]
            cause_summary=data["cause_summary"],  # type: ignore[arg-type]
            task_type=data.get("task_type"),  # type: ignore[arg-type]
            attempt_count=data["attempt_count"],  # type: ignore[arg-type]
            first_seen=data["first_seen"],  # type: ignore[arg-type]
            last_seen=data["last_seen"],  # type: ignore[arg-type]
            resolution=data.get("resolution"),  # type: ignore[arg-type]
            resolved=data.get("resolved", False),  # type: ignore[arg-type]
            extra=data.get("extra", {}),  # type: ignore[arg-type]
        )


@dataclass
class SimilarFailure:
    record: FailureRecord
    similarity: float  # 1.0 for an exact signature match; Jaccard score otherwise


class FailureMemoryStore:
    def __init__(self, state_dir: str = ".goldenboy", filename: str = "failures.json"):
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, filename)

    def _load(self) -> Dict[str, FailureRecord]:
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise FailureMemoryError(
                f"Failure-memory file at '{self.state_file}' is corrupted ({e}). "
                "Remove it to start fresh."
            ) from e
        except OSError as e:
            raise FailureMemoryError(f"Could not read failure-memory file at '{self.state_file}': {e}") from e

        records = data.get("records", {}) if isinstance(data, dict) else {}
        result: Dict[str, FailureRecord] = {}
        for sig, raw in records.items():
            try:
                result[sig] = FailureRecord.from_dict(raw)
            except (KeyError, TypeError):
                continue
        return result

    def _save(self, records: Dict[str, FailureRecord]) -> None:
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        payload = {
            "schema_version": FAILURE_MEMORY_SCHEMA_VERSION,
            "records": {sig: r.to_dict() for sig, r in records.items()},
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def record(self, cause_summary: str, task_type: Optional[str] = None) -> FailureRecord:
        """Record one failure occurrence. If a record with the same
        normalized signature already exists, increments its
        `attempt_count` rather than creating a duplicate."""
        safe_cause = redact_secrets(cause_summary)
        sig = _signature(safe_cause)
        records = self._load()
        now = _utcnow_iso()

        if sig in records:
            records[sig].attempt_count += 1
            records[sig].last_seen = now
        else:
            records[sig] = FailureRecord(
                schema_version=FAILURE_MEMORY_SCHEMA_VERSION,
                signature=sig,
                cause_summary=safe_cause,
                task_type=task_type,
                attempt_count=1,
                first_seen=now,
                last_seen=now,
            )

        self._save(records)
        return records[sig]

    def resolve(self, signature: str, resolution: str) -> Optional[FailureRecord]:
        records = self._load()
        if signature not in records:
            return None
        records[signature].resolution = redact_secrets(resolution)
        records[signature].resolved = True
        self._save(records)
        return records[signature]

    def load_all(self) -> List[FailureRecord]:
        return list(self._load().values())

    def find_similar(self, cause_summary: str, min_similarity: float = 0.4) -> List[SimilarFailure]:
        """Exact-signature matches first (similarity 1.0), then any other
        record whose keyword overlap with `cause_summary` is at or above
        `min_similarity`, most similar first."""
        sig = _signature(cause_summary)
        query_keywords = _keywords(cause_summary)
        records = self._load()

        results: List[SimilarFailure] = []
        for record_sig, record in records.items():
            if record_sig == sig:
                results.append(SimilarFailure(record=record, similarity=1.0))
                continue
            score = _jaccard(query_keywords, _keywords(record.cause_summary))
            if score >= min_similarity:
                results.append(SimilarFailure(record=record, similarity=score))

        results.sort(key=lambda s: -s.similarity)
        return results

    def clear(self) -> None:
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
