"""
Unified LLM client — two-tier routing, cloud-only.

Single entry point for every LLM call in the project. Wraps the OpenAI
SDK and routes through OpenRouter (default) or OpenAI direct.

═══ Tiers ═══════════════════════════════════════════════════════════════════
 FAST    — DeepSeek V4 Flash (default). Structured JSON, decisions, annotations,
           reconciliation, prose diagnostics, scene validation. Latency-
           sensitive. Quality is bounded by JSON schema, so a smaller/faster
           model is fine.
 QUALITY — DeepSeek V4 Pro (default). Turn narration, milestone reflections,
           time-skip prose, studio generation. Quality-critical, latency-tolerant.

═══ Configuration ═══════════════════════════════════════════════════════════
  CLOUD_PROVIDER     = openrouter | openai     (default: openrouter)
  FAST_MODEL         = deepseek/deepseek-v4-flash
  QUALITY_MODEL      = deepseek/deepseek-v4-pro
  OPENROUTER_API_KEY = sk-or-...

Per-call-site overrides (optional, named by purpose):
  NARRATION_MODEL, DECISION_MODEL, ANNOTATION_MODEL, RECONCILIATION_MODEL,
  DIAGNOSTIC_MODEL, MILESTONE_MODEL, STUDIO_MODEL, MEMORY_MODEL,
  CHOICE_QUALITY_MODEL, DRIFT_MODEL

Legacy back-compat:
  CLOUD_MODEL → if set, used as quality default.

═══ Architectural invariants ════════════════════════════════════════════════
- One quality-tier call per turn (narration). Fast-tier calls are accounted
  separately — they're structured JSON decisions.
- All hot-path calls have retry-with-fallback semantics.
- The call site chooses the tier; the client never auto-downgrades.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator, Optional

from openai import OpenAI


# ── Tier names ───────────────────────────────────────────────────────

TIER_FAST    = "fast"
TIER_QUALITY = "quality"


# ── Provider ─────────────────────────────────────────────────────────

CLOUD_PROVIDER    = os.getenv("CLOUD_PROVIDER", "openrouter")

PROVIDER_BASE_URLS = {
    "openai":     None,
    "openrouter": "https://openrouter.ai/api/v1",
}


# ── Model configuration ──────────────────────────────────────────────

# New tiered configuration (preferred path)
FAST_MODEL    = os.getenv("FAST_MODEL",    "deepseek/deepseek-v4-flash")
QUALITY_MODEL = os.getenv("QUALITY_MODEL", "deepseek/deepseek-v4-pro")

# Legacy single-cloud-model knob — if set, used as the quality default.
# Lets existing deployments keep working without env-var migration.
_LEGACY_CLOUD_MODEL = os.getenv("CLOUD_MODEL", "")
if _LEGACY_CLOUD_MODEL:
    QUALITY_MODEL = _LEGACY_CLOUD_MODEL

# Per-call-site overrides — empty string means "fall through to tier default"
PURPOSE_OVERRIDES = {
    "narration":      os.getenv("NARRATION_MODEL",      FAST_MODEL),
    "decision":       os.getenv("DECISION_MODEL",       ""),
    "annotation":     os.getenv("ANNOTATION_MODEL",     ""),
    "reconciliation": os.getenv("RECONCILIATION_MODEL", ""),
    "diagnostic":     os.getenv("DIAGNOSTIC_MODEL",     ""),
    "milestone":      os.getenv("MILESTONE_MODEL",      ""),
    "studio":         os.getenv("STUDIO_MODEL",         ""),
    "memory":         os.getenv("MEMORY_MODEL",         ""),
    "choice_quality": os.getenv("CHOICE_QUALITY_MODEL", ""),
    "choice_repair":  os.getenv("CHOICE_REPAIR_MODEL",  ""),
    "drift":          os.getenv("DRIFT_MODEL",          ""),
    "polarity":       os.getenv("POLARITY_MODEL",       ""),
    "epilogue":       os.getenv("EPILOGUE_MODEL",       ""),
    "recap":          os.getenv("RECAP_MODEL",          ""),
}


# ── OpenRouter app attribution ───────────────────────────────────────
# Helps OpenRouter rank the app and gives observability into usage.
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Storyteller-V3")
OPENROUTER_APP_URL  = os.getenv("OPENROUTER_APP_URL",
                                 "https://github.com/storyteller-v3")


# ── OpenRouter provider preferences ──────────────────────────────────
# require_parameters=true: OpenRouter will only route to providers that
#   support ALL request parameters (e.g. json_schema, seed). Without this,
#   strict JSON schema requests can silently fall through to providers
#   that don't enforce the schema, breaking studio generation.
# data_collection: "deny" excludes providers that log requests for training.
#   "allow" permits them (cheaper). Default to deny for production safety.
OPENROUTER_REQUIRE_PARAMS = os.getenv("OPENROUTER_REQUIRE_PARAMS", "true").lower() == "true"
OPENROUTER_DATA_COLLECTION = os.getenv("OPENROUTER_DATA_COLLECTION", "deny")  # deny | allow
OPENROUTER_PROVIDER_ORDER = [
    provider.strip()
    for provider in os.getenv("OPENROUTER_PROVIDER_ORDER", "").split(",")
    if provider.strip()
]
OPENROUTER_PROVIDER_ONLY = [
    provider.strip()
    for provider in os.getenv("OPENROUTER_PROVIDER_ONLY", "").split(",")
    if provider.strip()
]
OPENROUTER_PROVIDER_IGNORE = [
    provider.strip()
    for provider in os.getenv("OPENROUTER_PROVIDER_IGNORE", "").split(",")
    if provider.strip()
]
OPENROUTER_PROVIDER_SORT = os.getenv("OPENROUTER_PROVIDER_SORT", "").strip()
_ALLOW_FALLBACKS_RAW = os.getenv("OPENROUTER_ALLOW_FALLBACKS", "").strip().lower()
OPENROUTER_ALLOW_FALLBACKS = (
    None if not _ALLOW_FALLBACKS_RAW else _ALLOW_FALLBACKS_RAW == "true"
)


# ── Token budgets ────────────────────────────────────────────────────

MAX_NARRATION_TOKENS = int(os.getenv("NARRATION_MAX_TOKENS", "1200"))
LLM_TIMING_LOG = os.getenv("LLM_TIMING_LOG", "true").lower() == "true"
LLM_USAGE_LOG = os.getenv("LLM_USAGE_LOG", "true").lower() == "true"


# ── Token usage accounting ───────────────────────────────────────────
# Per-purpose running totals for the process lifetime. Cost optimization
# is impossible to evaluate without knowing where the tokens actually go,
# so every successful completion records its usage here and emits an
# LLM_USAGE log line. `cached_prompt_tokens` surfaces provider prefix-cache
# hits (OpenAI-style prompt_tokens_details.cached_tokens, or DeepSeek's
# native prompt_cache_hit_tokens) — the signal that prompt restructuring
# for cache stability is working.

_USAGE_TOTALS: dict[str, dict] = {}


def _extract_usage(response) -> Optional[dict]:
    """Pull token counts off a chat completion response, defensively.

    Providers disagree on where cached-prefix counts live; check the
    OpenAI shape first, then DeepSeek's native field.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details is not None else None
    if cached is None:
        cached = getattr(usage, "prompt_cache_hit_tokens", None)

    return {
        "prompt_tokens":         getattr(usage, "prompt_tokens", None),
        "completion_tokens":     getattr(usage, "completion_tokens", None),
        "total_tokens":          getattr(usage, "total_tokens", None),
        "cached_prompt_tokens":  cached,
    }


def log_llm_usage(*, purpose: str, tier: str, model: str, response) -> None:
    """Record and log token usage for a successful completion.

    Safe to call with any response object — silently no-ops when the
    provider didn't return usage data.
    """
    usage = _extract_usage(response)
    if usage is None:
        return

    key = purpose or tier
    bucket = _USAGE_TOTALS.setdefault(key, {
        "calls": 0, "prompt_tokens": 0,
        "completion_tokens": 0, "cached_prompt_tokens": 0,
    })
    bucket["calls"] += 1
    for field in ("prompt_tokens", "completion_tokens", "cached_prompt_tokens"):
        value = usage.get(field)
        if isinstance(value, (int, float)):
            bucket[field] += int(value)

    if LLM_USAGE_LOG:
        logging.info(
            "LLM_USAGE purpose=%s tier=%s model=%s prompt_tokens=%s "
            "completion_tokens=%s cached_prompt_tokens=%s",
            purpose or "-", tier, model,
            usage["prompt_tokens"], usage["completion_tokens"],
            usage["cached_prompt_tokens"],
        )


def usage_totals() -> dict:
    """Per-purpose token totals for this process. For /health and eval runs."""
    return {key: dict(bucket) for key, bucket in _USAGE_TOTALS.items()}


def _log_llm_timing(
    *,
    purpose: str,
    tier: str,
    model: str,
    elapsed: float,
    ok: bool,
    kind: str,
) -> None:
    if not LLM_TIMING_LOG:
        return
    logging.info(
        "LLM_TIMING kind=%s purpose=%s tier=%s model=%s ok=%s elapsed_sec=%.2f",
        kind, purpose or "-", tier, model, ok, elapsed,
    )


# ── Retry-after / backoff helpers ────────────────────────────────────
# Mirrors gm/cloud_gm.py._retry_after_seconds — keeps the narration path
# and the structured-JSON / fast-tier path in sync. OpenRouter returns
# rate-limit hints in two places: the standard HTTP `Retry-After` header
# and `error.metadata.retry_after_seconds` in the response body. We honor
# both, capped at 30s. Without server guidance we fall back to exponential
# backoff capped at 20s.

_RETRY_AFTER_CAP_SEC = 30.0
_BACKOFF_CAP_SEC     = 20.0
_BACKOFF_BASE_SEC    = 2.0


def _retry_after_seconds(error: Exception) -> Optional[float]:
    """Extract a server-provided retry-after delay from a provider error.

    Reads (in order):
      1. The `Retry-After` HTTP header on the response object.
      2. `error.metadata.retry_after_seconds` from the JSON body
         (OpenRouter convention).

    Returns None when neither is present or the values are unparseable.
    """
    response = getattr(error, "response", None)
    if response is None:
        return None

    headers = getattr(response, "headers", None)
    if headers is not None:
        header_value: Optional[str] = None
        try:
            header_value = headers.get("retry-after") or headers.get("Retry-After")
        except Exception:  # noqa: BLE001 — header containers vary by SDK
            header_value = None
        if header_value is not None:
            try:
                return float(header_value)
            except (TypeError, ValueError):
                pass

    json_loader = getattr(response, "json", None)
    if callable(json_loader):
        try:
            data = json_loader()
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, dict):
            metadata = (data.get("error") or {}).get("metadata") or {}
            value = metadata.get("retry_after_seconds")
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    return None


def _is_transient_error(error: Exception) -> bool:
    """Returns True when an error looks worth retrying (rate-limit / 5xx / timeout)."""
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    if status in {408, 409, 429, 500, 502, 503, 504}:
        return True
    text = str(error).lower()
    return any(token in text for token in ("rate", "timeout", "temporarily", "overloaded"))


def _compute_backoff_seconds(error: Exception, attempt: int) -> float:
    """Pick the wait time before the next retry.

    Server-provided Retry-After (capped at 30s) wins. Without it, fall back
    to exponential backoff (2s * 2^attempt) capped at 20s. Always at least
    0.5s to avoid hammering a recovering provider.
    """
    parsed = _retry_after_seconds(error)
    if parsed is not None:
        return max(0.5, min(parsed, _RETRY_AFTER_CAP_SEC))
    return max(0.5, min(_BACKOFF_BASE_SEC * (2 ** attempt), _BACKOFF_CAP_SEC))


# ── Model capability registry ────────────────────────────────────────
# Encodes provider-specific quirks behind a stable interface. New models
# get a one-line entry; call sites keep their `tier=fast|quality` calls
# unchanged. The registry is matched by prefix, longest-prefix-wins.

# Reasoning families. Each entry says how the model expects reasoning
# config to be passed:
#   - "openai_effort":    `reasoning_effort` top-level kwarg + max_completion_tokens
#   - "openrouter_object": `reasoning: {effort: ...}` inside extra_body
#   - "openrouter_disabled": `reasoning: {enabled: false}` inside extra_body
#   - None / "none":      No reasoning support; ignore reasoning hints.
MODEL_CAPABILITIES: list[tuple[str, dict]] = [
    # OpenAI reasoning models
    ("gpt-5",  {"reasoning": "openai_effort", "max_param": "max_completion_tokens"}),
    ("gpt-o",  {"reasoning": "openai_effort", "max_param": "max_completion_tokens"}),
    ("o1-",    {"reasoning": "openai_effort", "max_param": "max_completion_tokens"}),
    ("o3-",    {"reasoning": "openai_effort", "max_param": "max_completion_tokens"}),
    # DeepSeek V4 (OpenRouter): Pro accepts effort, Flash uses defaults
    ("deepseek/deepseek-v4-pro",   {"reasoning": "openrouter_object", "max_param": "max_tokens"}),
    ("deepseek/deepseek-v4-flash", {"reasoning": "none",              "max_param": "max_tokens"}),
    # Interactive narration should not spend latency/budget on hidden thinking.
    ("moonshotai/kimi-k2.6",         {"reasoning": "openrouter_disabled", "max_param": "max_tokens"}),
    ("google/gemini-3-flash-preview", {"reasoning": "openrouter_disabled", "max_param": "max_tokens"}),
    ("x-ai/grok-4.1-fast",          {"reasoning": "openrouter_disabled", "max_param": "max_tokens"}),
    ("x-ai/grok-4.20",              {"reasoning": "openrouter_disabled", "max_param": "max_tokens"}),
    # Anthropic via OpenRouter
    ("anthropic/", {"reasoning": "none", "max_param": "max_tokens"}),
    # Standard fallback (DeepSeek non-V4, Llama, Mistral, Qwen-cloud, etc.)
    ("",       {"reasoning": "none", "max_param": "max_tokens"}),
]


def _capabilities_for(model: str) -> dict:
    """Return capability dict for a model, by longest-matching prefix."""
    m = model.lower()
    best: tuple[int, dict] = (-1, MODEL_CAPABILITIES[-1][1])
    for prefix, caps in MODEL_CAPABILITIES:
        if not prefix or m.startswith(prefix):
            if len(prefix) > best[0]:
                best = (len(prefix), caps)
    return best[1]


def _is_reasoning_model(model: str) -> bool:
    """Backward-compat helper. New code should use _capabilities_for(model)."""
    return _capabilities_for(model)["reasoning"] != "none"


# ── Public API ───────────────────────────────────────────────────────


def resolve_model(*, tier: str, purpose: str = "") -> str:
    """Pick the actual model id for a tier+purpose.

    Resolution order:
      1. {PURPOSE}_MODEL env override (if set)
      2. tier default (FAST_MODEL or QUALITY_MODEL)
    """
    override = PURPOSE_OVERRIDES.get(purpose, "")
    if override:
        return override

    return FAST_MODEL if tier == TIER_FAST else QUALITY_MODEL


def make_client() -> OpenAI:
    """OpenAI-compatible client for the configured cloud provider."""
    if CLOUD_PROVIDER == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        return OpenAI(
            base_url=PROVIDER_BASE_URLS["openrouter"],
            api_key=api_key,
            default_headers={
                "HTTP-Referer": OPENROUTER_APP_URL,
                "X-Title":      OPENROUTER_APP_NAME,
            },
        )

    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


def _prepare_kwargs(
    *,
    model: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    timeout: float,
    seed: Optional[int],
    response_format: Optional[dict],
    extra: Optional[dict],
) -> dict:
    """Build the kwargs dict for chat.completions.create.

    Encodes provider quirks in one place:
      - max_tokens vs max_completion_tokens (depends on model family)
      - reasoning_effort vs extra_body.reasoning (OpenAI vs OpenRouter)
      - extra_body.provider for OpenRouter routing preferences
    Call sites stay clean — they pass (model, messages, ...) and the right
    provider syntax happens here.
    """
    caps = _capabilities_for(model)
    kwargs: dict = {
        "model":       model,
        "messages":    messages,
        "temperature": temperature,
        "timeout":     timeout,
    }
    extra_body: dict = {}

    # Token budget — different param name for reasoning models
    kwargs[caps["max_param"]] = max_tokens

    # Reasoning configuration — only for models that support it
    reasoning_effort = os.getenv("REASONING_EFFORT", "low")
    if reasoning_effort and caps["reasoning"] == "openai_effort":
        kwargs["reasoning_effort"] = reasoning_effort
    elif reasoning_effort and caps["reasoning"] == "openrouter_object":
        extra_body["reasoning"] = {"effort": reasoning_effort}
    elif caps["reasoning"] == "openrouter_disabled":
        extra_body["reasoning"] = {"enabled": False}
    # else: model doesn't support reasoning — ignore the hint

    # OpenRouter provider preferences (require_parameters, data_collection)
    if CLOUD_PROVIDER == "openrouter":
        provider_block: dict = {}
        if OPENROUTER_REQUIRE_PARAMS:
            provider_block["require_parameters"] = True
        if OPENROUTER_DATA_COLLECTION:
            provider_block["data_collection"] = OPENROUTER_DATA_COLLECTION
        if OPENROUTER_PROVIDER_ORDER:
            provider_block["order"] = OPENROUTER_PROVIDER_ORDER
        if OPENROUTER_PROVIDER_ONLY:
            provider_block["only"] = OPENROUTER_PROVIDER_ONLY
        if OPENROUTER_PROVIDER_IGNORE:
            provider_block["ignore"] = OPENROUTER_PROVIDER_IGNORE
        if OPENROUTER_PROVIDER_SORT:
            provider_block["sort"] = OPENROUTER_PROVIDER_SORT
        if OPENROUTER_ALLOW_FALLBACKS is not None:
            provider_block["allow_fallbacks"] = OPENROUTER_ALLOW_FALLBACKS
        if provider_block:
            extra_body["provider"] = provider_block

    if extra_body:
        kwargs["extra_body"] = extra_body
    if response_format:
        kwargs["response_format"] = response_format
    if seed is not None:
        kwargs["seed"] = seed
    if extra:
        # Merge extra_kwargs from caller. If they pass extra_body, deep-merge.
        if "extra_body" in extra and "extra_body" in kwargs:
            merged = {**kwargs["extra_body"], **extra["extra_body"]}
            kwargs["extra_body"] = merged
            extra = {k: v for k, v in extra.items() if k != "extra_body"}
        kwargs.update(extra)

    return kwargs


def call_chat(
    *,
    tier: str,
    user: str,
    purpose: str = "",
    system: Optional[str] = None,
    response_format: Optional[dict] = None,
    temperature: float = 0.4,
    max_tokens: int = 1500,
    seed: Optional[int] = None,
    timeout: float = 60.0,
    retries: int = 3,
    extra_kwargs: Optional[dict] = None,
) -> str:
    """Single-call chat completion. Returns the assistant's text content.

    Raises RuntimeError on persistent failure (after `retries` attempts).
    """
    model  = resolve_model(tier=tier, purpose=purpose)
    client = make_client()

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs = _prepare_kwargs(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, seed=seed,
        response_format=response_format, extra=extra_kwargs,
    )

    last_error: Optional[Exception] = None
    started = time.time()
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(**kwargs)
            content  = response.choices[0].message.content
            if content is None or not content.strip():
                raise RuntimeError(f"Empty content from {model}")
            log_llm_usage(purpose=purpose, tier=tier, model=model, response=response)
            _log_llm_timing(
                purpose=purpose,
                tier=tier,
                model=model,
                elapsed=time.time() - started,
                ok=True,
                kind="chat",
            )
            return content.strip()
        except Exception as e:  # noqa: BLE001 — provider SDK exceptions vary
            last_error = e
            logging.warning(
                "LLM call failed (purpose=%s tier=%s attempt=%d/%d model=%s): %s",
                purpose or "-", tier, attempt + 1, retries, model, e,
            )
            if attempt < retries - 1 and _is_transient_error(e):
                delay = _compute_backoff_seconds(e, attempt)
                logging.warning(
                    "Transient provider error — sleeping %.1fs before retry "
                    "(purpose=%s tier=%s model=%s)",
                    delay, purpose or "-", tier, model,
                )
                time.sleep(delay)

    _log_llm_timing(
        purpose=purpose,
        tier=tier,
        model=model,
        elapsed=time.time() - started,
        ok=False,
        kind="chat",
    )
    raise RuntimeError(
        f"LLM call failed after {retries} attempts "
        f"(purpose={purpose} tier={tier} model={model}): {last_error}"
    ) from last_error


def call_chat_json(
    *,
    tier: str,
    user: str,
    purpose: str = "",
    system: Optional[str] = None,
    schema: Optional[dict] = None,
    schema_name: str = "response",
    temperature: float = 0.2,
    max_tokens: int = 1500,
    seed: Optional[int] = None,
    timeout: float = 60.0,
    retries: int = 3,
    strict_schema: bool = True,
) -> dict:
    """JSON-mode chat call. Parses and returns a dict.

    Uses OpenAI-compatible json_schema response_format. With
    OPENROUTER_REQUIRE_PARAMS=true (default), OpenRouter routes to a
    provider that actually enforces the schema, eliminating the
    json.loads-then-cross-fingers retry loop the project used to need.

    When strict_schema=False (or the API rejects json_schema), falls back
    to json_object mode with the schema injected into the prompt as guidance.
    """
    use_strict = bool(strict_schema and schema)
    if use_strict:
        response_format: dict = {
            "type": "json_schema",
            "json_schema": {
                "name":   schema_name,
                "schema": schema,
                "strict": True,
            },
        }
        user_prompt = user
    else:
        response_format = {"type": "json_object"}
        user_prompt = user
        if schema:
            user_prompt += (
                "\n\nReturn ONLY a JSON object matching this schema. "
                "No prose, no markdown, no code fences:\n"
                f"{json.dumps(schema, indent=2)}\n"
            )

    last_error: Optional[Exception] = None
    last_text: str = ""

    for attempt in range(retries):
        try:
            text = call_chat(
                tier=tier, purpose=purpose,
                user=user_prompt,
                system=system,
                response_format=response_format,
                temperature=temperature, max_tokens=max_tokens,
                seed=seed, timeout=timeout, retries=1,
            )
            last_text = text

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            return json.loads(text)
        except (json.JSONDecodeError, RuntimeError) as e:
            last_error = e
            logging.warning(
                "JSON LLM call failed (purpose=%s attempt=%d/%d strict=%s): %s | first 300 chars: %s",
                purpose or "-", attempt + 1, retries, use_strict, e, last_text[:300],
            )
            # If strict json_schema failed, try json_object on the next attempt
            # (some providers don't yet support json_schema even with require_parameters).
            if use_strict and attempt == 0:
                use_strict = False
                response_format = {"type": "json_object"}
                user_prompt = user + (
                    "\n\nReturn ONLY a JSON object matching this schema. "
                    "No prose, no markdown, no code fences:\n"
                    f"{json.dumps(schema, indent=2)}\n"
                )

            # call_chat wraps provider errors in RuntimeError with __cause__;
            # introspect that for rate-limit hints. JSON-decode failures don't
            # carry server hints, so they fall through to default backoff.
            if attempt < retries - 1:
                root = getattr(e, "__cause__", None) or e
                if _is_transient_error(root):
                    delay = _compute_backoff_seconds(root, attempt)
                    logging.warning(
                        "JSON LLM transient error — sleeping %.1fs before retry "
                        "(purpose=%s)",
                        delay, purpose or "-",
                    )
                    time.sleep(delay)

    raise RuntimeError(
        f"JSON LLM call failed after {retries} attempts "
        f"(purpose={purpose}): {last_error}"
    ) from last_error


def call_chat_stream(
    *,
    tier: str,
    user: str,
    purpose: str = "",
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = MAX_NARRATION_TOKENS,
    timeout: float = 60.0,
    extra_kwargs: Optional[dict] = None,
) -> Iterator[str]:
    """Streaming chat completion. Yields content delta strings."""
    model  = resolve_model(tier=tier, purpose=purpose)
    client = make_client()

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs = _prepare_kwargs(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, seed=None,
        response_format=None, extra=extra_kwargs,
    )
    kwargs["stream"] = True

    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ── Diagnostic helpers ───────────────────────────────────────────────


def describe_routing() -> dict:
    """Return the active routing configuration. Useful for /health endpoints."""
    return {
        "provider":      CLOUD_PROVIDER,
        "fast_model":    resolve_model(tier=TIER_FAST),
        "quality_model": resolve_model(tier=TIER_QUALITY),
        "narration_model": resolve_model(tier=TIER_QUALITY, purpose="narration"),
        "narration_max_tokens": MAX_NARRATION_TOKENS,
        "overrides":     {k: v for k, v in PURPOSE_OVERRIDES.items() if v},
        "usage_totals":  usage_totals(),
    }
