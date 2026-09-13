"""Golden Boy's own exception types.

Kept deliberately small: one base class plus one per user-facing failure
mode that previously surfaced as a raw traceback (malformed config,
corrupted checkpoint). CLI commands catch `GoldenBoyError` at the boundary
and print `str(exc)` instead of a stack trace — so these messages are
written for a developer reading a terminal, not for logging internals.
"""


class GoldenBoyError(Exception):
    """Base class for errors Golden Boy raises deliberately (as opposed to
    an unexpected bug). CLI commands catch this and print it cleanly."""


class ConfigError(GoldenBoyError):
    """The config file or an environment override could not be loaded, or
    resolved to a value outside its documented valid range."""


class CheckpointError(GoldenBoyError):
    """The checkpoint file is missing required data, corrupted, or from an
    incompatible future version."""
