import pytest

from goldenboy.core.config import reset_default_config


@pytest.fixture(autouse=True)
def _reset_goldenboy_config_cache():
    """`get_default_config()` caches process-wide so repeated Budget/Estimator/
    RiskEngine construction doesn't re-read config on every call. Without this
    reset, a test that sets GOLDENBOY_* env vars or writes .goldenboy/config.json
    could leak its config into a later test that never touches either, purely
    because the cache was already warm."""
    reset_default_config()
    yield
    reset_default_config()
