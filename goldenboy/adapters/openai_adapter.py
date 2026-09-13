import logging
import os
import time
from typing import Callable, Optional

from openai import OpenAI

from goldenboy.adapters.base import ProviderAdapter, confidence_for_age
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.config import GoldenBoyConfig, get_default_config

logger = logging.getLogger("goldenboy.adapters.openai")

# Model used only for the tiny refresh probe below — never for real work.
# Pinned to a cheap model since the response content is discarded; only
# the rate-limit response headers are read.
_PROBE_MODEL = "gpt-4o-mini"


class OpenAIAdapter(ProviderAdapter):
    """
    Reports usage for OpenAI's API by reading the
    `x-ratelimit-remaining-tokens` / `-limit-tokens` response headers.

    Important: these headers describe the account/org's shared rate-limit
    bucket, not "how much of this coding session/context is left" — an
    org can have most of its per-minute token bucket free while an
    individual agent session is nearly out of context. Budgets from this
    adapter are reported with `confidence=UNKNOWN` before the first
    refresh, `ESTIMATED` while the last refresh is still within
    `GoldenBoyConfig.stale_after_seconds`, and `STALE` once it's aged past
    that — `source="openai_rate_limit_headers"` always, for exactly this
    reason: never treat these as an exact session budget.

    Usage numbers are only as fresh as the last `refresh_usage()` call.
    This adapter does not execute coding work (see `ProviderAdapter`) and
    does not call the API automatically on every `get_available_budget()`
    — refreshing costs a real (tiny) API call, so it's explicit.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        safety_margin: Optional[float] = None,
        config: Optional[GoldenBoyConfig] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIAdapter")

        self.client = OpenAI(api_key=self.api_key)
        self._safety_margin_override = safety_margin
        self.config = config or get_default_config()
        # time.monotonic (not time.time): measuring elapsed duration, not
        # wall-clock position -- immune to system clock adjustments.
        # Overridable so tests can advance time deterministically instead
        # of sleeping.
        self._clock: Callable[[], float] = clock or time.monotonic

        self._current_remaining_tokens: Optional[float] = None
        self._total_allowed_tokens: Optional[float] = None
        self._last_refresh_at: Optional[float] = None

    def _update_limits_from_headers(self, headers) -> bool:
        """Parse rate-limit headers. Returns True if both values were present."""
        remaining = headers.get("x-ratelimit-remaining-tokens")
        total = headers.get("x-ratelimit-limit-tokens")

        if remaining is None or total is None:
            logger.warning(
                "OpenAI response did not include rate-limit headers; "
                "usage estimate left unchanged."
            )
            return False

        self._current_remaining_tokens = float(remaining)
        self._total_allowed_tokens = float(total)
        self._last_refresh_at = self._clock()
        return True

    def refresh_usage(self) -> bool:
        """Make one minimal API call solely to read current rate-limit
        headers and update the cached usage estimate. Returns True on
        success. Costs a small number of real tokens; call it explicitly
        (e.g. periodically, or from `goldenboy doctor`) rather than on
        every budget check.
        """
        try:
            response = self.client.chat.completions.with_raw_response.create(
                model=_PROBE_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return self._update_limits_from_headers(response.headers)
        except Exception as e:
            logger.warning("OpenAI usage refresh failed: %s", e)
            return False

    def get_available_budget(self) -> Budget:
        kwargs = {}
        if self._safety_margin_override is not None:
            kwargs["safety_margin"] = self._safety_margin_override

        # All three fields are always set together by _update_limits_from_headers;
        # checking all of them (not just total) keeps that invariant explicit
        # rather than implicit, and satisfies the type checker that neither
        # `remaining` nor `_last_refresh_at` is None below.
        if (
            self._total_allowed_tokens is None
            or self._current_remaining_tokens is None
            or self._last_refresh_at is None
            or self._total_allowed_tokens <= 0
        ):
            # Never refreshed yet: we genuinely don't know the usage state.
            return Budget(
                remaining_percentage=100.0,
                total_allowed=None,
                source="openai_rate_limit_headers",
                confidence=UsageConfidence.UNKNOWN,
                **kwargs,
            )

        percentage = (self._current_remaining_tokens / self._total_allowed_tokens) * 100.0
        age = self._clock() - self._last_refresh_at
        return Budget(
            remaining_percentage=percentage,
            total_allowed=self._total_allowed_tokens,
            source="openai_rate_limit_headers",
            confidence=confidence_for_age(age, self.config.stale_after_seconds),
            **kwargs,
        )
