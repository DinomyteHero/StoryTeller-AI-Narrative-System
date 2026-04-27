"""Unit tests for retry-after / exponential-backoff helpers in gm.llm_client.

These cover the rate-limit handling that prevents 429 warning storms in the
fast-tier choice-quality path. Provider-side 429s arrive with hints in two
places — the standard HTTP `Retry-After` header and OpenRouter's
`error.metadata.retry_after_seconds` body field — and we honor both.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gm.llm_client import (
    _BACKOFF_BASE_SEC,
    _BACKOFF_CAP_SEC,
    _RETRY_AFTER_CAP_SEC,
    _compute_backoff_seconds,
    _is_transient_error,
    _retry_after_seconds,
    call_chat,
)


# ── Stub error scaffolding ───────────────────────────────────────────


class _StubHeaders:
    def __init__(self, headers: dict | None = None):
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}

    def get(self, key, default=None):
        value = self._headers.get(key.lower())
        return default if value is None else value


class _StubResponse:
    def __init__(self, *, headers=None, body=None, status_code=429):
        self.headers = _StubHeaders(headers)
        self._body = body
        self.status_code = status_code

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class _StubProviderError(Exception):
    """Mirrors the shape of OpenAI/httpx errors: .response, .status_code."""

    def __init__(self, message: str, *, response: _StubResponse | None = None,
                 status_code: int | None = None):
        super().__init__(message)
        self.response = response
        self.status_code = status_code if status_code is not None else (
            getattr(response, "status_code", None)
        )


# ── _retry_after_seconds ─────────────────────────────────────────────


def test_retry_after_reads_http_header():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(headers={"Retry-After": "7"}),
    )
    assert _retry_after_seconds(err) == 7.0


def test_retry_after_reads_lowercase_header():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(headers={"retry-after": "3.5"}),
    )
    assert _retry_after_seconds(err) == 3.5


def test_retry_after_reads_openrouter_metadata():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(
            body={"error": {"metadata": {"retry_after_seconds": 12}}},
        ),
    )
    assert _retry_after_seconds(err) == 12.0


def test_retry_after_header_wins_over_body():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(
            headers={"Retry-After": "4"},
            body={"error": {"metadata": {"retry_after_seconds": 99}}},
        ),
    )
    assert _retry_after_seconds(err) == 4.0


def test_retry_after_returns_none_when_absent():
    err = _StubProviderError("rate limited", response=_StubResponse())
    assert _retry_after_seconds(err) is None


def test_retry_after_handles_unparseable_values():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(headers={"Retry-After": "soon"}),
    )
    assert _retry_after_seconds(err) is None


def test_retry_after_no_response_attribute():
    assert _retry_after_seconds(RuntimeError("boom")) is None


# ── _is_transient_error ──────────────────────────────────────────────


def test_is_transient_status_code_429():
    err = _StubProviderError("rate limited", status_code=429)
    assert _is_transient_error(err) is True


def test_is_transient_status_code_via_response():
    err = _StubProviderError("server error",
                             response=_StubResponse(status_code=503))
    assert _is_transient_error(err) is True


def test_is_transient_message_keywords():
    assert _is_transient_error(RuntimeError("Request timeout"))
    assert _is_transient_error(RuntimeError("provider overloaded"))
    assert _is_transient_error(RuntimeError("rate limit exceeded"))


def test_is_transient_rejects_400_class_other_than_429():
    err = _StubProviderError("bad request", status_code=400)
    assert _is_transient_error(err) is False


def test_is_transient_rejects_unrelated_error():
    assert _is_transient_error(ValueError("malformed")) is False


# ── _compute_backoff_seconds ─────────────────────────────────────────


def test_backoff_uses_retry_after_when_present():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(headers={"Retry-After": "9"}),
    )
    assert _compute_backoff_seconds(err, attempt=0) == 9.0


def test_backoff_caps_retry_after_at_30s():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(headers={"Retry-After": "120"}),
    )
    assert _compute_backoff_seconds(err, attempt=0) == _RETRY_AFTER_CAP_SEC


def test_backoff_falls_back_to_exponential_without_hint():
    err = _StubProviderError("rate limited", status_code=429)
    # attempt 0: 2.0 * 2^0 = 2.0
    assert _compute_backoff_seconds(err, attempt=0) == _BACKOFF_BASE_SEC
    # attempt 1: 2.0 * 2 = 4.0
    assert _compute_backoff_seconds(err, attempt=1) == _BACKOFF_BASE_SEC * 2
    # attempt 5 would be 64s — capped at 20s
    assert _compute_backoff_seconds(err, attempt=5) == _BACKOFF_CAP_SEC


def test_backoff_floor_is_half_second():
    err = _StubProviderError(
        "rate limited",
        response=_StubResponse(headers={"Retry-After": "0"}),
    )
    assert _compute_backoff_seconds(err, attempt=0) == 0.5


# ── Integration: call_chat actually sleeps between retries ───────────


class _FlakyClient:
    """OpenAI-shaped stub that fails N times with a 429, then succeeds."""

    def __init__(self, fail_times: int, retry_after: float | None = None):
        self.fail_times = fail_times
        self.retry_after = retry_after
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **_kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            headers = {"Retry-After": str(self.retry_after)} if self.retry_after else {}
            raise _StubProviderError(
                "rate limited",
                response=_StubResponse(headers=headers, status_code=429),
            )

        class _Choice:
            class message:
                content = "ok"
        class _Resp:
            choices = [_Choice()]
        return _Resp()


def test_call_chat_sleeps_between_retries_on_429(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda d: sleeps.append(d))
    monkeypatch.setattr("gm.llm_client.make_client",
                        lambda: _FlakyClient(fail_times=1, retry_after=2))

    result = call_chat(tier="fast", user="hi", retries=2)
    assert result == "ok"
    assert sleeps == [2.0]


def test_call_chat_does_not_sleep_on_non_transient_error(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda d: sleeps.append(d))

    class _Bad:
        chat = None
        completions = None

        def __init__(self):
            self.chat = self
            self.completions = self
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            raise ValueError("malformed prompt")

    monkeypatch.setattr("gm.llm_client.make_client", _Bad)

    try:
        call_chat(tier="fast", user="hi", retries=2)
    except RuntimeError:
        pass
    assert sleeps == []  # no backoff on non-transient errors
