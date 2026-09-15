# The Golden Boy Protocol

A versioned, language-neutral JSON schema for the one thing every Golden
Boy consumer actually needs: a decision. It's the payload `goldenboy
analyze --json` prints, what `goldenboy.core.decision_engine.DecisionEngine.decide()`
returns (as a `goldenboy.protocol.GoldenBoyDecision`), and what
`sdk/typescript`'s `GoldenBoyClient.analyze()` parses on the TypeScript
side. There is exactly one definition of this shape per language
(`goldenboy/protocol.py` for Python, `sdk/typescript/src/types.ts` for
TypeScript) — they're kept in sync by hand, the same convention
`skills/goldenboy/SKILL.md` already uses to stay in sync with
`goldenboy.core.risk.ExecutionMode`.

`schemas/decision.schema.json` formalizes this shape as an actual JSON
Schema (draft-07), so "kept in sync by hand" has an automated check behind
it: `tests/test_protocol_schema.py` validates real `DecisionEngine` output
against it and cross-checks the schema's `required`/`enum` values against
what `goldenboy.protocol` enforces; `sdk/typescript/test/schema.test.ts`
does the equivalent on the TypeScript side, exercising `parseDecision`
against every field the schema marks required. The schema doesn't replace
either implementation (neither reads it at runtime) — it's a shared,
versioned reference the two are tested against, per language.

## Design goals

- **Versioned.** Every payload carries `schema_version` (currently
  `"1.0.0"`). A reader only refuses a payload whose *major* version it
  doesn't understand — additive, backward-compatible fields bump
  minor/patch and don't break older readers.
- **Provider- and language-independent.** Plain JSON: strings, numbers,
  booleans, arrays, and nested objects. No custom types, no references to
  Python- or TypeScript-specific concepts leak into the wire format.
- **Strictly validated.** Both `GoldenBoyDecision.from_dict` (Python) and
  `parseDecision` (TypeScript) raise a specific error
  (`ProtocolError`/`goldenboy.core.errors.GoldenBoyError` on the Python
  side, `ProtocolError` on the TypeScript side) naming the exact missing
  field or version mismatch — never a raw `KeyError`/`TypeError`.
- **No network dependency.** The protocol module itself
  (`goldenboy/protocol.py`) has zero imports beyond the Python standard
  library; nothing about the schema requires an HTTP server (see
  ["Why no server"](#why-no-server) below).

## Schema

```jsonc
{
  "schema_version": "1.0.0",
  "generated_at": "2026-09-14T06:06:46.403936+00:00",   // ISO 8601, UTC

  "task": {
    "task_type": "bug_fix",                // one of goldenboy.core.task_types.TaskType
    "task_type_confidence": 0.72,           // heuristic match-strength, 0.0-1.0 -- NOT a calibrated probability
    "complexity": 0.05,                     // estimated_cost_percentage / 100, clamped to [0, 1]
    "complexity_label": "LOW",              // LOW | MEDIUM | HIGH | VERY_HIGH
    "estimated_cost_percentage": 5.0,       // Estimator's real, measured estimate
    "estimated_cost_confidence": 0.85,      // 0.85 with tiktoken installed, 0.50 on the fallback heuristic
    "signals": { "bug_fix:\\bbugs?\\b": 2 } // which keyword patterns matched, for transparency/debugging
  },

  "usage": {
    "remaining_percentage": 50.0,
    "usable_percentage": 47.0,              // remaining_percentage - safety_margin, floored at 0
    "source": "mock",                       // "mock" | "anthropic_rate_limit_headers" | "openai_rate_limit_headers" | ...
    "confidence": "EXACT"                   // EXACT | ESTIMATED | STALE | UNKNOWN
  },

  "risk": {
    "mode": "SAFE",                         // SAFE | CAUTION | LIMITED | CRITICAL (goldenboy.core.risk.ExecutionMode)
    "reason_code": "COST_TO_BUDGET_RATIO_BELOW_CAUTION_THRESHOLD",
    "ratio": 0.106                          // estimated_cost / usable_percentage, or null when usable is 0
  },

  "action": "run",           // RUN | CONTINUE | REDUCE_SCOPE | FINISH | VERIFY | STOP | ASK_USER (lowercase on the wire)
  "confidence": 0.95,        // blended decision confidence, 0.0-1.0 -- see DecisionEngine's docstring for the exact formula
  "reason": "Task classified as bug_fix (LOW complexity, estimated cost 5.0% of budget, confidence 0.85). ...",
  "recommendation": [
    "Proceed with the task as scoped."
  ]
}
```

Every field in `task`/`usage`/`risk` is required; `recommendation`
defaults to `[]` if omitted. See `goldenboy/protocol.py` for the
authoritative dataclass definitions and exact validation rules, and
`sdk/typescript/src/types.ts` for the equivalent TypeScript interfaces.

### `risk.reason_code` values

Produced by `DecisionEngine`, re-deriving *which* branch of
`RiskEngine.assess()` fired (read-only introspection — `RiskEngine` itself
still makes the actual decision; see its own docstring):

| Code | Meaning |
|---|---|
| `BUDGET_AT_OR_BELOW_SAFETY_MARGIN` | `Budget.is_exhausted()` — CRITICAL |
| `ESTIMATED_COST_EXCEEDS_USABLE_BUDGET` | required > usable — LIMITED |
| `COST_TO_BUDGET_RATIO_AT_OR_ABOVE_CAUTION_THRESHOLD` | ratio ≥ `caution_ratio` — CAUTION |
| `COST_TO_BUDGET_RATIO_BELOW_CAUTION_THRESHOLD` | ratio < `caution_ratio` — SAFE |

Any of these may carry a `_THEN_UNKNOWN_CONFIDENCE_DOWNGRADE` suffix when
`DecisionEngine`'s own conservative-UNKNOWN-confidence policy overrode an
otherwise-SAFE verdict (see `decision_engine.py`'s module docstring for
why that policy lives there and not in `RiskEngine`).

## Getting a decision

**CLI:**
```bash
goldenboy analyze "Refactor the auth module" --budget 15 --json
```

**Python:**
```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.to_json())
```

**TypeScript:**
```ts
import { GoldenBoyClient } from "@goldenboy/sdk";
const decision = await new GoldenBoyClient().analyze("Refactor the auth module", { budget: 15 });
```

All three produce the identical schema above — the CLI's JSON output *is*
`GoldenBoyDecision.to_dict()` serialized, and the TypeScript client parses
that same JSON back through `parseDecision`.

## Why no server

Every transport here is either a Python function call, CLI stdout, or a
spawned child process reading stdout (`sdk/typescript`) — there is no HTTP
server, socket, or daemon anywhere in this protocol. That's a deliberate
choice: local stdin/stdout/IPC is sufficient for "one process asks Golden
Boy for one decision," and a server would add a process-lifecycle,
port-management, and auth surface with no corresponding benefit for that
use case. Revisit only if a concrete need for network-transparent access
(e.g. a remote agent orchestrator) actually appears.

## Versioning policy

- A breaking change (a field removed, renamed, or given a new meaning)
  bumps the **major** version and updates `PROTOCOL_VERSION` in both
  `goldenboy/protocol.py` and `sdk/typescript/src/types.ts` together, in
  the same change.
- An additive, backward-compatible change (a new optional field) bumps
  minor/patch only. Readers on an older minor version simply ignore
  fields they don't recognize (both `from_dict` implementations only
  validate *required* fields, not that the payload contains nothing
  extra).
- `from_dict`/`parseDecision` reject a payload whose major version differs
  from what they implement, with a `ProtocolError` naming both versions —
  never a silent misread.
