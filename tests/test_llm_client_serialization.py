"""Serialization tests for the LLM client request-body construction.

The brief from the wiring audit verified that gm.llm_client's retry/backoff
helpers are correct. It did not verify what the client actually sends to
the provider — and request-body shape is where OpenAI-compatible code
most often breaks (max_tokens vs max_completion_tokens, reasoning_effort
vs extra_body.reasoning, OpenRouter provider preferences).

These tests exercise _prepare_kwargs across model families without making
network calls. The live smoke class at the bottom is gated by
RUN_LIVE_LLM=1 — it makes a single short call to the configured provider
to verify the constructed body is actually accepted end-to-end.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gm import llm_client
from gm.llm_client import _prepare_kwargs, call_chat


def _openrouter_defaults(monkeypatch):
    """Force the routing constants to known values for kwargs tests."""
    monkeypatch.setattr(llm_client, "CLOUD_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "OPENROUTER_REQUIRE_PARAMS", True)
    monkeypatch.setattr(llm_client, "OPENROUTER_DATA_COLLECTION", "deny")
    monkeypatch.setattr(llm_client, "OPENROUTER_PROVIDER_ORDER", [])
    monkeypatch.setattr(llm_client, "OPENROUTER_PROVIDER_ONLY", [])
    monkeypatch.setattr(llm_client, "OPENROUTER_PROVIDER_IGNORE", [])
    monkeypatch.setattr(llm_client, "OPENROUTER_PROVIDER_SORT", "")
    monkeypatch.setattr(llm_client, "OPENROUTER_ALLOW_FALLBACKS", None)


def _kwargs_for(model: str, **overrides):
    base = dict(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.4,
        max_tokens=128,
        timeout=60.0,
        seed=None,
        response_format=None,
        extra=None,
    )
    base.update(overrides)
    return _prepare_kwargs(model=model, **base)


# ── max_tokens vs max_completion_tokens ──────────────────────────────


class TestMaxTokenParam:
    def test_gpt5_uses_max_completion_tokens(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setenv("REASONING_EFFORT", "low")
        kwargs = _kwargs_for("gpt-5.2")
        assert "max_completion_tokens" in kwargs
        assert "max_tokens" not in kwargs
        assert kwargs["max_completion_tokens"] == 128

    def test_deepseek_pro_uses_max_tokens(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for("deepseek/deepseek-v4-pro")
        assert "max_tokens" in kwargs
        assert "max_completion_tokens" not in kwargs

    def test_deepseek_flash_uses_max_tokens(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash")
        assert "max_tokens" in kwargs
        assert "max_completion_tokens" not in kwargs

    def test_anthropic_uses_max_tokens(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for("anthropic/claude-opus-4.7")
        assert "max_tokens" in kwargs
        assert "max_completion_tokens" not in kwargs


# ── reasoning configuration ──────────────────────────────────────────


class TestReasoningShape:
    def test_gpt5_uses_top_level_reasoning_effort(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setenv("REASONING_EFFORT", "low")
        kwargs = _kwargs_for("gpt-5.2")
        assert kwargs.get("reasoning_effort") == "low"
        eb = kwargs.get("extra_body") or {}
        assert "reasoning" not in eb, (
            "OpenAI reasoning models must use top-level reasoning_effort, "
            "not extra_body.reasoning"
        )

    def test_deepseek_pro_uses_extra_body_reasoning(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setenv("REASONING_EFFORT", "low")
        kwargs = _kwargs_for("deepseek/deepseek-v4-pro")
        assert "reasoning_effort" not in kwargs
        assert kwargs["extra_body"]["reasoning"] == {"effort": "low"}

    def test_kimi_disables_reasoning(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setenv("REASONING_EFFORT", "low")
        kwargs = _kwargs_for("moonshotai/kimi-k2.6")
        assert kwargs["extra_body"]["reasoning"] == {"enabled": False}

    def test_deepseek_flash_no_reasoning_block(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setenv("REASONING_EFFORT", "low")
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash")
        eb = kwargs.get("extra_body") or {}
        assert "reasoning" not in eb


# ── OpenRouter provider preferences ──────────────────────────────────


class TestOpenRouterProviderBlock:
    def test_default_provider_block_has_require_and_data_collection(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash")
        provider = kwargs["extra_body"]["provider"]
        assert provider["require_parameters"] is True
        assert provider["data_collection"] == "deny"

    def test_provider_order_propagates(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setattr(
            llm_client, "OPENROUTER_PROVIDER_ORDER", ["deepseek", "fireworks"]
        )
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash")
        assert kwargs["extra_body"]["provider"]["order"] == ["deepseek", "fireworks"]

    def test_provider_only_propagates(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setattr(llm_client, "OPENROUTER_PROVIDER_ONLY", ["deepseek"])
        kwargs = _kwargs_for("deepseek/deepseek-v4-pro")
        assert kwargs["extra_body"]["provider"]["only"] == ["deepseek"]

    def test_allow_fallbacks_propagates_when_set(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setattr(llm_client, "OPENROUTER_ALLOW_FALLBACKS", False)
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash")
        assert kwargs["extra_body"]["provider"]["allow_fallbacks"] is False

    def test_openai_provider_has_no_provider_block(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        monkeypatch.setattr(llm_client, "CLOUD_PROVIDER", "openai")
        kwargs = _kwargs_for("gpt-5.2")
        eb = kwargs.get("extra_body") or {}
        assert "provider" not in eb, (
            "OpenRouter-only routing knobs must not leak into OpenAI requests"
        )


# ── response_format and seed pass-through ─────────────────────────────


class TestResponseFormatAndSeed:
    def test_response_format_is_attached_when_provided(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        rf = {"type": "json_object"}
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash", response_format=rf)
        assert kwargs["response_format"] == rf

    def test_seed_is_attached_when_provided(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash", seed=42)
        assert kwargs["seed"] == 42

    def test_seed_omitted_when_none(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for("deepseek/deepseek-v4-flash", seed=None)
        assert "seed" not in kwargs


# ── extra_kwargs deep-merge ──────────────────────────────────────────


class TestExtraKwargsMerge:
    def test_extra_body_is_deep_merged(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for(
            "deepseek/deepseek-v4-flash",
            extra={"extra_body": {"custom_field": "value"}},
        )
        eb = kwargs["extra_body"]
        assert eb["custom_field"] == "value"
        assert "provider" in eb, (
            "deep-merge must not drop the provider block we built"
        )

    def test_top_level_extra_kwargs_pass_through(self, monkeypatch):
        _openrouter_defaults(monkeypatch)
        kwargs = _kwargs_for(
            "deepseek/deepseek-v4-flash",
            extra={"top_p": 0.95},
        )
        assert kwargs["top_p"] == 0.95


# ── Live smoke (only when RUN_LIVE_LLM=1) ─────────────────────────────


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM") != "1",
    reason="Set RUN_LIVE_LLM=1 to exercise the real provider end-to-end",
)
class TestLiveProvider:
    """Asserts the request body we construct is accepted by the actual
    provider. Uses the real env (CLOUD_PROVIDER / API key) — does not
    monkeypatch the routing constants."""

    def test_fast_tier_one_word_round_trip(self):
        out = call_chat(
            tier="fast",
            user="Reply with the single word: PING",
            max_tokens=8,
            temperature=0.0,
            timeout=20.0,
            retries=1,
        )
        assert out is not None, "Live call returned None"
        assert len(out.strip()) > 0, "Live call returned empty content"
