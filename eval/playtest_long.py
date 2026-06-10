"""Long-run playtest harness — depth-pass stress test through Acts 2-3.

Plays 30-40 turns of Shadows of the Custodian reaching at least Act 3, mixing
authored choice picks with 2-3 free-form actions per act. After every turn it
snapshots the parts of `arc_state` the depth pass added, so the resulting log
is a frozen record of how the new mechanics behaved over a long session.

Outputs:
  - A snapshot log (JSON-lines, one entry per turn) at the configured path.
  - A short markdown report capturing per-act behavior of the depth-pass
    mechanics and a Star Wars fan readability/immersion read.

Run:
  1) Start the engine, e.g. `uvicorn api.main:app --port 8765`
     with cloud credentials available in the environment.
  2) `python eval/playtest_long.py --turns 35 --report docs/research/...md`

The harness is best-effort: any per-turn API error is logged and the run
continues so the report still captures partial behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_BASE = "http://127.0.0.1:8765"
DEFAULT_LOG  = Path("eval/playtest_long_snapshots.jsonl")


# ── HTTP helpers ─────────────────────────────────────────────────────


class Engine:
    def __init__(self, base: str = DEFAULT_BASE):
        self.base = base.rstrip("/")

    def post(self, path: str, body: dict | None = None, *, timeout: float = 300.0) -> dict:
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def get(self, path: str, *, timeout: float = 30.0) -> dict:
        req = urllib.request.Request(f"{self.base}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))


# ── Snapshot model ───────────────────────────────────────────────────


@dataclass
class TurnSnapshot:
    turn_number: int
    label: str
    elapsed_sec: float
    error: str = ""
    narration_excerpt: str = ""
    choices: list[str] = field(default_factory=list)
    check_made: bool = False
    outcome: str = ""

    # Depth-pass surfaces (read off arc_state after the turn lands)
    current_act: int = 1
    act_progress: float = 0.0
    memorable_moments: list[dict] = field(default_factory=list)
    thread_state: dict = field(default_factory=dict)
    tactical_state: dict = field(default_factory=dict)
    faction_emergent: dict = field(default_factory=dict)
    contradiction_arc: dict = field(default_factory=dict)
    pivots_fired: list[str] = field(default_factory=list)
    foreshadow_payoffs: list[str] = field(default_factory=list)
    side_content_engaged: list[str] = field(default_factory=list)
    # Brooks/Weiland arc tracking (added with the framework integration)
    lie_grip: float | None = None
    arc_movements_count: int = 0
    arc_recent_kind: str = ""


def _excerpt(text: str | None, n: int = 240) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def snapshot_from(
    *,
    turn_number: int,
    label: str,
    elapsed: float,
    turn_payload: dict,
    arc_state: dict,
    character: dict | None = None,
) -> TurnSnapshot:
    snap = TurnSnapshot(turn_number=turn_number, label=label, elapsed_sec=elapsed)

    snap.narration_excerpt = _excerpt(
        turn_payload.get("narration") or turn_payload.get("opening_narration", "")
    )
    snap.choices = list(turn_payload.get("choices") or [])

    dice = turn_payload.get("dice_result") or {}
    snap.check_made = bool(dice)
    roll = turn_payload.get("roll_summary") or ""
    if isinstance(roll, str) and roll:
        snap.outcome = roll[:80]

    snap.current_act = int(arc_state.get("current_act", 1) or 1)
    snap.act_progress = float(arc_state.get("act_progress", 0.0) or 0.0)
    snap.memorable_moments = list(arc_state.get("memorable_moments") or [])
    snap.thread_state = dict(arc_state.get("thread_state") or {})
    snap.tactical_state = dict(arc_state.get("tactical_state") or {})
    snap.faction_emergent = dict(arc_state.get("faction_emergent") or {})
    snap.contradiction_arc = dict(arc_state.get("contradiction_arc") or {})
    snap.pivots_fired = list(arc_state.get("pivots_fired") or [])
    snap.foreshadow_payoffs = list(arc_state.get("foreshadow_payoffs_delivered") or [])
    snap.side_content_engaged = list(arc_state.get("side_content_engaged") or [])
    if isinstance(character, dict):
        nar = character.get("narrative_arc") or {}
        if nar:
            try:
                snap.lie_grip = float(nar.get("lie_grip"))
            except (TypeError, ValueError):
                snap.lie_grip = None
            mv = nar.get("movements") or []
            snap.arc_movements_count = len(mv)
            if mv:
                snap.arc_recent_kind = str(mv[-1].get("kind", ""))
    return snap


# ── Choice plan ──────────────────────────────────────────────────────


# Mix of cautious / bold / curious choices and free-form actions, designed
# to keep the loop moving toward Act 3. The harness clamps `index` against
# the actual choice count, and falls through to free-form on a stuck loop.
PLAN: list[dict] = [
    # ── Act 1: investigation seed + first signs of Kira's drift ──────
    {"kind": "choice", "index": 0, "tag": "act1.opening"},
    {"kind": "choice", "index": 1},
    {"kind": "freeform", "text":
        "Walk to Tionne's archive and stand outside the door for a full minute. "
        "Listen to whatever she's working on before knocking. Investigate the "
        "old Massassi material she has been quietly cataloguing."},
    {"kind": "choice", "index": 2},
    {"kind": "choice", "index": 0},
    {"kind": "freeform", "text":
        "Probe Kira about where she goes after lights-out. Trace her route from "
        "the dorms toward the lower temple and observe — don't confront her yet."},
    {"kind": "choice", "index": 1},
    # ── Act 2: pressure rises, imperial signals appear ───────────────
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 2},
    {"kind": "freeform", "text":
        "Question the mechanic about the imperial transponder still wired to the "
        "shuttle. Ask whether she's ever heard a real reply on it. Report what "
        "she says to Tionne."},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 1},
    {"kind": "freeform", "text":
        "Warn Luke privately about the Massassi vault and the imperial echoes — "
        "but ask him not to confront Kira yet. Shelter her until you understand."},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 2},
    # ── Act 3: confrontation, descent, Kira disclosure pivot ─────────
    {"kind": "choice", "index": 0},
    {"kind": "freeform", "text":
        "Descend into the lower Massassi levels with Kira. Don't accuse — let "
        "her walk you to whatever she wants you to see. Use Sense to feel for "
        "the truth around her answers as she leads."},
    {"kind": "choice", "index": 1},
    {"kind": "choice", "index": 0},
    {"kind": "freeform", "text":
        "Tell Kira directly: I know about Malakai. Then go quiet and wait. Don't "
        "fill the silence."},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 2},
    {"kind": "choice", "index": 1},
    # ── Act 3 escalation / combat scene if it fires ──────────────────
    {"kind": "choice", "index": 0},
    {"kind": "freeform", "text":
        "If Tannen's task force breaches the perimeter, position myself between "
        "the students and the breach. Defend the corridor, don't hunt the "
        "stormtroopers — buy time for evacuation."},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 1},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 2},
    {"kind": "choice", "index": 1},
    # ── Late Act 3 / spillover into Act 4 ────────────────────────────
    {"kind": "freeform", "text":
        "After the dust settles, sit with Kira in the wrecked archive and ask "
        "her what she actually wants — not what she's been told to want."},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 1},
    {"kind": "freeform", "text":
        "Take the three blank prayer beads off and set one of them on the "
        "altar in the wrecked archive. Whatever I am after this, the aunt "
        "wouldn't recognise it without the gesture."},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 0},
    {"kind": "choice", "index": 1},
    {"kind": "choice", "index": 0},
]


# ── Pending offer resolution ─────────────────────────────────────────


def resolve_pending(engine: Engine, sid: str, data: dict) -> dict:
    """Roll forward through any pending interactive offer until we hit a normal turn."""
    while data.get("pending"):
        if data.get("temptation_offer"):
            offer = data["temptation_offer"]
            # Reject dark temptations, accept light/inverted by default.
            accept = not offer.get("is_dark_temptation", False)
            data = engine.post(f"/session/{sid}/temptation", {"accept": accept})
            continue
        if data.get("intervention_offer"):
            data = engine.post(f"/session/{sid}/intervention", {"accept": True})
            continue
        # Nothing matched; bail to avoid infinite loop
        break

    if data.get("milestone"):
        ms = data["milestone"]
        choices = ms.get("choices") or []
        if choices:
            ref = choices[0].get("talent_ref", "")
            data = engine.post(f"/session/{sid}/milestone", {"talent_ref": ref})

    return data


# ── Main play loop ───────────────────────────────────────────────────


def run(
    *,
    base: str = DEFAULT_BASE,
    turns: int = 35,
    log_path: Path = DEFAULT_LOG,
    campaign_name: str = "shadows_of_the_custodian",
    character_id: str = "clovis_beryl",
) -> list[TurnSnapshot]:
    engine = Engine(base)
    print(f"[playtest] base={base} turns={turns} campaign={campaign_name} "
          f"character={character_id} log={log_path}")

    sess = engine.post("/session", {
        "campaign_name": campaign_name,
        "character_id":  character_id,
    })
    sid = sess["session_id"]
    last_choices = sess.get("choices", [])
    print(f"[playtest] session_id={sid} opening_choices={len(last_choices)}")

    snapshots: list[TurnSnapshot] = []

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as logf:
        # opening as turn 0
        sess_full = engine.get(f"/session/{sid}")
        opening_snap = snapshot_from(
            turn_number=0,
            label="opening",
            elapsed=0.0,
            turn_payload=sess,
            arc_state=sess_full.get("arc_state", {}),
            character=sess_full.get("character", {}),
        )
        snapshots.append(opening_snap)
        logf.write(json.dumps(opening_snap.__dict__) + "\n")
        logf.flush()

        for n in range(1, turns + 1):
            step = PLAN[(n - 1) % len(PLAN)]
            if step["kind"] == "freeform":
                body = {"choice_index": -1, "free_form_action": step["text"]}
                label = f"freeform: {step['text'][:48]}"
            else:
                idx = step["index"]
                if idx >= len(last_choices):
                    idx = max(0, len(last_choices) - 1)
                body = {"choice_index": idx}
                label = (
                    f"choice {idx}: "
                    f"{(last_choices[idx] if last_choices else '<no choices>')[:48]}"
                )

            t0 = time.time()
            err = ""
            try:
                data = engine.post(f"/session/{sid}/turn", body)
                data = resolve_pending(engine, sid, data)
            except urllib.error.HTTPError as e:
                try:
                    err = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
                except Exception:
                    err = f"HTTP {e.code}"
                data = {}
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
                data = {}

            elapsed = time.time() - t0

            # Pull arc_state + character via GET so we always have the
            # canonical post-turn view, including the live narrative_arc.
            try:
                full_session = engine.get(f"/session/{sid}")
                arc_state = full_session.get("arc_state", {})
                char_dict = full_session.get("character", {})
            except Exception as e:  # noqa: BLE001
                arc_state = {}
                char_dict = {}
                err = err or f"arc_state fetch failed: {e}"

            snap = snapshot_from(
                turn_number=n,
                label=label,
                elapsed=elapsed,
                turn_payload=data,
                arc_state=arc_state,
                character=char_dict,
            )
            snap.error = err
            snapshots.append(snap)
            logf.write(json.dumps(snap.__dict__) + "\n")
            logf.flush()

            print(
                f"[turn {n:02d}] {elapsed:5.1f}s "
                f"act={snap.current_act} prog={snap.act_progress:.2f} "
                f"threads={len(snap.thread_state)} "
                f"moments={len(snap.memorable_moments)} "
                f"factions={len(snap.faction_emergent)} "
                f"pivots={len(snap.pivots_fired)} "
                f"err={'Y' if err else '.'}"
            )

            if err:
                # If we lost the session entirely, abandon. Otherwise we continue.
                if "404" in err or "session not found" in err.lower():
                    print(f"[playtest] session lost — stopping early")
                    break
            last_choices = data.get("choices") or last_choices

    return snapshots


# ── Report writer ────────────────────────────────────────────────────


_STOPWORDS = {
    "the", "and", "for", "with", "into", "this", "that", "from", "have", "has",
    "had", "but", "she", "his", "her", "its", "are", "was", "were", "been",
    "they", "them", "their", "there", "then", "than", "your", "you", "him",
    "out", "off", "now", "not", "all", "any", "one", "two", "any", "some",
    "kira", "tionne", "luke", "praxeum", "mechanic", "student",
}


def _moment_keywords(moment: dict) -> set[str]:
    """Pull distinctive (≥5-char, non-stopword) tokens out of a memorable-moment summary."""
    text = " ".join([
        str(moment.get("summary") or ""),
        str(moment.get("trigger") or ""),
    ]).lower()
    out: set[str] = set()
    for tok in text.replace(",", " ").replace(".", " ").replace("'", " ").split():
        if len(tok) < 5:
            continue
        if tok in _STOPWORDS:
            continue
        out.add(tok)
    return out


def detect_callbacks(snapshots: list[TurnSnapshot]) -> list[dict]:
    """Heuristic: did any memorable-moment summary's distinctive words later
    surface in a narration excerpt? Returns one entry per detected callback.
    """
    out: list[dict] = []
    seen_moments: list[tuple[int, dict, set[str]]] = []  # (first_seen_turn, moment, keywords)
    for snap in snapshots:
        # Register any new moments visible after this turn.
        for m in snap.memorable_moments:
            if not isinstance(m, dict):
                continue
            mid = m.get("id") or m.get("summary", "")[:40]
            if any(s[1].get("id", s[1].get("summary", "")[:40]) == mid for s in seen_moments):
                continue
            seen_moments.append((snap.turn_number, m, _moment_keywords(m)))

        # Look for callbacks in this turn's narration excerpt — only against
        # moments captured strictly *before* this turn.
        narration = (snap.narration_excerpt or "").lower()
        if not narration:
            continue
        for first_turn, moment, keywords in seen_moments:
            if first_turn >= snap.turn_number:
                continue
            hits = [k for k in keywords if k in narration]
            if len(hits) >= 2:  # require ≥2 distinctive hits to filter coincidence
                out.append({
                    "callback_turn": snap.turn_number,
                    "moment_origin_turn": first_turn,
                    "moment_summary": (moment.get("summary") or "")[:120],
                    "matched_tokens": hits[:6],
                })
    return out


def _summarize(snapshots: list[TurnSnapshot]) -> dict:
    """Compute the top-line numbers the report needs."""
    by_act: dict[int, list[TurnSnapshot]] = {}
    for s in snapshots:
        by_act.setdefault(s.current_act, []).append(s)

    combat_active = any(
        s.tactical_state.get("kind") == "combat"
        for s in snapshots
    )
    combat_round_max = max(
        (int(s.tactical_state.get("round", 0) or 0)
         for s in snapshots if s.tactical_state.get("kind") == "combat"),
        default=0,
    )
    tactical_kinds_seen = sorted({
        s.tactical_state.get("kind", "")
        for s in snapshots
        if s.tactical_state.get("kind")
    })
    tactical_stage_progression: dict[str, list[str]] = {}
    for s in snapshots:
        kind = s.tactical_state.get("kind") or ""
        stage = s.tactical_state.get("stage") or ""
        if kind and stage:
            stages = tactical_stage_progression.setdefault(kind, [])
            if not stages or stages[-1] != stage:
                stages.append(stage)

    contradiction_movements_max = max(
        (int(s.contradiction_arc.get("movements", 0) or 0) for s in snapshots),
        default=0,
    )
    pivots_fired = sorted({p for s in snapshots for p in s.pivots_fired})
    payoffs_delivered = sorted({p for s in snapshots for p in s.foreshadow_payoffs})

    moments_total = max((len(s.memorable_moments) for s in snapshots), default=0)
    threads_total = max((len(s.thread_state) for s in snapshots), default=0)
    factions_seen = sorted({f for s in snapshots for f in s.faction_emergent})
    side_content_engaged = sorted({c for s in snapshots for c in s.side_content_engaged})

    errors = [s for s in snapshots if s.error]

    callbacks = detect_callbacks(snapshots)

    return {
        "turns": len(snapshots) - 1,  # exclude opening
        "by_act": {a: len(v) for a, v in by_act.items()},
        "combat_active": combat_active,
        "combat_round_max": combat_round_max,
        "tactical_kinds_seen": tactical_kinds_seen,
        "tactical_stage_progression": tactical_stage_progression,
        "contradiction_movements_max": contradiction_movements_max,
        "pivots_fired": pivots_fired,
        "act3_kira_pivot_fired": "act3_kira_disclosure_pivot" in pivots_fired,
        "payoffs_delivered": payoffs_delivered,
        "moments_total": moments_total,
        "threads_total": threads_total,
        "factions_seen": factions_seen,
        "side_content_engaged": side_content_engaged,
        "callbacks": callbacks,
        "errors": [{"turn": s.turn_number, "error": s.error} for s in errors],
    }


def write_report(
    *,
    snapshots: list[TurnSnapshot],
    out_path: Path,
    extra_notes: str = "",
) -> None:
    summary = _summarize(snapshots)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Depth-pass stress test — long run\n\n")
        f.write(f"Turns played: **{summary['turns']}**  \n")
        f.write(f"Acts reached: **{sorted(summary['by_act'])}** "
                f"(turns per act: {summary['by_act']})  \n")
        f.write(f"Errors: **{len(summary['errors'])}**\n\n")

        f.write("## Depth-pass mechanics — did they activate?\n\n")
        f.write(f"- **Tactical state — kinds seen:** "
                f"{', '.join(summary['tactical_kinds_seen']) or '—'}\n")
        for kind, stages in summary["tactical_stage_progression"].items():
            f.write(f"  - `{kind}` stage progression: {' → '.join(stages)}\n")
        f.write(f"- **Combat tactical state engaged:** "
                f"{'YES' if summary['combat_active'] else 'no'}"
                f" (max rounds: {summary['combat_round_max']})\n")
        f.write(f"- **Act 3 Kira disclosure pivot fired:** "
                f"{'YES' if summary['act3_kira_pivot_fired'] else 'no'}"
                f" (all pivots: {summary['pivots_fired'] or '—'})\n")
        f.write(f"- **Contradiction-arc movements (max during run):** "
                f"{summary['contradiction_movements_max']}\n")
        f.write(f"- **Memorable moments captured (max):** {summary['moments_total']}\n")
        f.write(f"- **Threads tracked (max):** {summary['threads_total']}\n")
        f.write(f"- **Faction emergent shifts seen on:** "
                f"{summary['factions_seen'] or '—'}\n")
        f.write(f"- **Foreshadow payoffs delivered:** "
                f"{summary['payoffs_delivered'] or '—'}\n")
        f.write(f"- **Side content engaged:** "
                f"{summary['side_content_engaged'] or '—'}\n")
        f.write(f"- **Memorable-moment callbacks detected in later prose:** "
                f"{len(summary['callbacks'])}\n\n")

        if summary["callbacks"]:
            f.write("### Detected callbacks\n\n")
            for c in summary["callbacks"]:
                f.write(
                    f"- Turn {c['callback_turn']} echoed moment from turn "
                    f"{c['moment_origin_turn']} "
                    f"(`{', '.join(c['matched_tokens'])}`): "
                    f"{c['moment_summary']}\n"
                )
            f.write("\n")

        if summary["errors"]:
            f.write("## Errors during the run\n\n")
            for e in summary["errors"]:
                f.write(f"- Turn {e['turn']}: `{e['error']}`\n")
            f.write("\n")

        f.write("## Per-turn arc-state trace\n\n")
        f.write("| Turn | Act | Prog | Threads | Moments | Factions | Pivots | Tactical | Note |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|---|---|\n")
        for s in snapshots:
            tac = s.tactical_state.get("kind", "—") if s.tactical_state else "—"
            note = "ERR" if s.error else ""
            f.write(
                f"| {s.turn_number} | {s.current_act} | {s.act_progress:.2f} "
                f"| {len(s.thread_state)} | {len(s.memorable_moments)} "
                f"| {len(s.faction_emergent)} | {len(s.pivots_fired)} "
                f"| {tac} | {note} |\n"
            )

        if extra_notes:
            f.write("\n## Star Wars fan readability and immersion notes\n\n")
            f.write(extra_notes.strip() + "\n")


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--turns", type=int, default=35)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument(
        "--campaign",
        default="shadows_of_the_custodian",
        help="Campaign slug from data/campaigns/ to play",
    )
    parser.add_argument(
        "--character",
        default="clovis_beryl",
        help="Character ID from data/characters/ to play as",
    )
    parser.add_argument(
        "--report", type=Path, default=None,
        help="Optional markdown report path. If not set, only the JSONL log is written.",
    )
    args = parser.parse_args()

    snapshots = run(
        base=args.base, turns=args.turns, log_path=args.log,
        campaign_name=args.campaign, character_id=args.character,
    )
    if args.report:
        write_report(snapshots=snapshots, out_path=args.report)
    print(f"[playtest] wrote {len(snapshots)} snapshots to {args.log}")
    if args.report:
        print(f"[playtest] wrote report to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
