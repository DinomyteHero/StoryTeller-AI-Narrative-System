"""Run one fixed Storyteller narration prompt against one OpenRouter model."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


PROMPT = """You are the narrator for Storyteller V3, a Star Wars-inspired narrative RPG using resolved mechanics.

Write the next passage in second person, present tense. Keep it 170-260 words. The dice and state are already resolved; do not change them.

PLAYER CHARACTER:
- A young Praxeum student on Yavin 4.
- Force Rating 1; basic Sense power.
- Curious, cautious, afraid of wanting power too much.

CURRENT SCENE:
- Dawn meditation in Luke Skywalker's Praxeum.
- Kira, another student, has been leaving before morning meditation.
- The player sensed heat and pressure beneath the Massassi temple: old Sith stone, a half-buried vergence, and something that noticed them.
- The player refused a dark-side temptation rather than take the easy clarity.
- Luke is present, calm but troubled. He will not give the player an easy answer.

PLAYER ACTION:
The player asks Luke what is under the temple and whether Kira might be drawn to it.

MECHANICAL OUTCOME TO HONOR:
- No new check this turn.
- Prior Force result revealed a real buried presence, but not a full answer.
- The player should gain one actionable lead and one emotional complication.

STYLE TARGET:
- Star Wars adventure tone, intimate rather than huge.
- Concrete sensory details.
- Coherent continuation, not a lore dump.
- Keep Luke compassionate and indirect.
- Do not mention dice, mechanics, tags, or model behavior in the passage.

After the passage, output exactly:
---CHOICES---
Then 3 choices, numbered. Put optional mechanical tags at the end in brackets only when appropriate, e.g. [Force:Sense], [Vigilance], [Discipline], [Perception].
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--outdir", default="__codex_model_audit")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument(
        "--provider-order",
        default="",
        help="Comma-separated OpenRouter provider order, e.g. deepseek,siliconflow.",
    )
    parser.add_argument(
        "--provider-ignore",
        default="",
        help="Comma-separated OpenRouter providers to ignore.",
    )
    parser.add_argument(
        "--allow-fallbacks",
        choices=["default", "true", "false"],
        default="default",
        help="Optional OpenRouter provider allow_fallbacks setting.",
    )
    parser.add_argument(
        "--data-collection",
        choices=["allow", "deny", "omit"],
        default="deny",
        help="OpenRouter provider data_collection setting.",
    )
    parser.add_argument(
        "--reasoning",
        choices=["none", "off", "low", "medium", "high"],
        default="none",
        help="Optional OpenRouter reasoning configuration.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENROUTER_API_KEY/OPENAI_API_KEY in environment or .env")

    from gm.cloud_gm import CloudGMError, _parse_response

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in args.label)
    outfile = outdir / f"{safe_label}.json"

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://github.com/storyteller-v3"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "Storyteller-V3"),
        },
    )

    started = time.time()
    record: dict = {
        "label": args.label,
        "model": args.model,
        "ok": False,
        "parse_ok": False,
        "elapsed_sec": None,
        "error": None,
        "passage_word_count": None,
        "choices": [],
        "skill_tags": [],
        "raw": None,
    }

    try:
        provider_block: dict = {}
        if args.data_collection != "omit":
            provider_block["data_collection"] = args.data_collection
        provider_order = [
            provider.strip()
            for provider in args.provider_order.split(",")
            if provider.strip()
        ]
        provider_ignore = [
            provider.strip()
            for provider in args.provider_ignore.split(",")
            if provider.strip()
        ]
        if provider_order:
            provider_block["order"] = provider_order
        if provider_ignore:
            provider_block["ignore"] = provider_ignore
        if args.allow_fallbacks != "default":
            provider_block["allow_fallbacks"] = args.allow_fallbacks == "true"

        extra_body: dict = {"provider": provider_block}
        if args.reasoning == "off":
            extra_body["reasoning"] = {"enabled": False}
        elif args.reasoning in {"low", "medium", "high"}:
            extra_body["reasoning"] = {"effort": args.reasoning}

        response = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=900,
            timeout=args.timeout,
            extra_body=extra_body,
        )
        record["elapsed_sec"] = round(time.time() - started, 2)
        record["response_shape"] = response.model_dump(mode="json", exclude_none=True)
        if not response.choices:
            record["error"] = "no choices returned"
            outfile.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps({k: record[k] for k in ("label", "model", "ok", "parse_ok", "elapsed_sec", "error", "choices", "skill_tags")}, ensure_ascii=False))
            return 0
        choice = response.choices[0]
        raw = choice.message.content or ""
        record["raw"] = raw
        record["finish_reason"] = choice.finish_reason
        record["ok"] = True
        try:
            parsed = _parse_response(raw)
            record["parse_ok"] = True
            record["passage_word_count"] = len(parsed.passage.split())
            record["passage"] = parsed.passage
            record["choices"] = parsed.choices
            record["skill_tags"] = parsed.skill_tags
        except CloudGMError as parse_error:
            record["error"] = f"parse: {parse_error}"
    except Exception as exc:
        record["elapsed_sec"] = round(time.time() - started, 2)
        record["error"] = str(exc)

    outfile.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("label", "model", "ok", "parse_ok", "elapsed_sec", "error", "choices", "skill_tags")}, ensure_ascii=False))
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
