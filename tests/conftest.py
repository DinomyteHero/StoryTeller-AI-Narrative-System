"""Suite-wide guards.

Tests are hermetic by default: live LLM credentials are stripped from the
environment for every test, so an accidentally unmocked call path fails
fast (and bills nobody) instead of silently reaching a provider. Several
route tests assert the 502-when-no-LLM contract and depended on this
implicitly — with working credentials in .env they would launch real,
slow, costed generation runs (the full-suite stall of 2026-06-10 was
tests/test_cs4_saga.py::TestCS4Routes::test_saga_route_exists running the
live 5-stage saga pipeline).

Opt into the live-LLM smoke tests explicitly with RUN_LIVE_LLM=1, which
leaves the environment untouched.
"""
import os

import pytest

_RUN_LIVE = os.getenv("RUN_LIVE_LLM", "").lower() in ("1", "true", "yes")

_LIVE_CREDENTIAL_VARS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "CLOUD_MODEL",
)


@pytest.fixture(autouse=True)
def _no_live_llm_credentials(monkeypatch):
    """Strip provider credentials per-test unless RUN_LIVE_LLM is set."""
    if not _RUN_LIVE:
        for var in _LIVE_CREDENTIAL_VARS:
            monkeypatch.delenv(var, raising=False)
    yield
