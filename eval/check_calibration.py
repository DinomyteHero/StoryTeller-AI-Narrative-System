"""Live check-decision calibration probe.

Calls gm.fast_gm.decide_check directly (no server, no narration calls)
with a battery of actions whose correct classification is known by
design: RISKY actions should trigger checks, TRIVIAL ones should not,
BORDERLINE ones may go either way. Reports trigger rates and the
model's per-action reasoning.

Use when changing the FAST-tier model, provider routing, or
gm/prompts/check_decision.txt — the design target for live play is
roughly 0.3-0.6 checks per turn, with risky/opposed actions reliably
triggering and routine conversation reliably not.

Run (live FAST-tier calls, ~12 small requests):
    python eval/check_calibration.py [--character data/characters/kessa_rhane.json]

History: first used 2026-06-09 to investigate an apparent 0-checks-in-
4-turns smoke result, which turned out to be response-field
misreading (the turn payload exposes dice under `dice_result` /
`roll_summary`; there is no `check` field). Battery result that day:
6/6 risky triggered, 0/3 trivial false-triggers.
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from engine.character import Character           # noqa: E402
from gm.fast_gm import decide_check              # noqa: E402

DEFAULT_CHARACTER = "data/characters/kessa_rhane.json"

SCENE = (
    "The Praxeum refectory at morning meal, eleven days into Kessa's provisional "
    "sanctuary. Thirty students, watchful staff. A nervous student — Dorin Vekk — has "
    "just slipped out early into the dim corridor beyond the serving hatch, one hand "
    "pressed against his ribs. Kam Solusar logs entries in his ledger at the staff "
    "table. The corridor outside is warm stone, low light, scattered with students "
    "moving between halls."
)

ARC = {"current_act": 1, "total_acts": 4,
       "act_name": "The Weight of the Name", "tension_level": "rising"}

BATTERY = [
    # (label, expected_check, action)
    ("risky/stealth-tail", True,
     "Follow Dorin into the corridor and shadow him without being seen — three meters back, soft feet, Catalogue tail discipline."),
    ("risky/grab-coerce", True,
     "Catch Dorin's arm before the stairwell, pin him against the wall, and press him hard: who else reads the reports he gives Kam? Make him answer."),
    ("risky/climb", True,
     "Scale the temple's rain-slick outer wall to reach the sealed third-level window before the patrol circles back."),
    ("risky/lie-to-kam", True,
     "Look Kam Solusar in the eye and lie about where I was last night — keep the cadence flat, give him nothing to log."),
    ("risky/slice", True,
     "Slice the practice droid's restraining bolt to override its safety limits before anyone notices me at the maintenance panel."),
    ("risky/saber-save", True,
     "Throw my training saber to knock the falling glow-lantern away from the younglings before it lands on them."),
    ("trivial/eat-talk", False,
     "Keep eating and answer Tahl's question honestly."),
    ("trivial/walk", False,
     "Finish my tray and walk to the archive after the meal."),
    ("trivial/tell-truth", False,
     "When Luke asks about the beacon, tell him the plain truth: I keep it where I can see it."),
    ("borderline/read-room", None,
     "Quietly read the refectory the way the Catalogue trained me — exits, sightlines, anyone whose attention is professional rather than curious."),
    ("borderline/meditate", None,
     "Sit at the edge of the meditation hall and steady myself before the staff hearing."),
    ("borderline/search-archive", None,
     "Search the archive shelves for any record that mentions Ossel Minor."),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", default=DEFAULT_CHARACTER)
    args = parser.parse_args()

    char = Character.model_validate(json.loads(
        Path(args.character).read_text(encoding="utf-8")))

    results = []
    for label, expected, action in BATTERY:
        try:
            d = decide_check(char, SCENE, action, ARC)
            results.append((label, expected, d.requires_check,
                            getattr(d, "skill", ""), d.reasoning))
        except Exception as e:
            results.append((label, expected, None, "", f"ERROR: {e}"))

    risky_hits = sum(1 for _, e, got, *_ in results if e is True and got is True)
    risky_total = sum(1 for _, e, *_ in results if e is True)
    false_triggers = sum(1 for _, e, got, *_ in results if e is False and got is True)
    trivial_total = sum(1 for _, e, *_ in results if e is False)

    print(f"RISKY triggered: {risky_hits}/{risky_total}   "
          f"TRIVIAL false-triggers: {false_triggers}/{trivial_total}")
    print("-" * 76)
    for label, expected, got, skill, reasoning in results:
        mark = ("OK " if (expected is None or got == expected) else "MISS")
        print(f"[{mark}] {label:26s} check={got!s:5s} skill={skill or '-':14s}")
        print(f"       {reasoning[:150]}")

    healthy = risky_hits >= risky_total - 1 and false_triggers == 0
    print("-" * 76)
    print("CALIBRATION:", "HEALTHY" if healthy else "NEEDS ATTENTION")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
