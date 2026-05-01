# Depth-pass stress test — long-run playtest through Act 4

**Date:** April 26, 2026
**Run:** 35 turns, single session, _Shadows of the Custodian_, character
`praxeum_student`. Models: `gpt-5.4-mini` (narration), `deepseek-v4-flash`
(fast tier), `deepseek-v4-pro` (quality tier — DeepSeek pivot live).
**Harness:** [eval/playtest_long.py](../../eval/playtest_long.py).
**Raw log:** [eval/playtest_long_snapshots.jsonl](../../eval/playtest_long_snapshots.jsonl).

This is the depth-pass follow-up the changelog called for: a long-run
playtest reaching Act 3 to pressure-test the new mechanics that the
April 26 10-turn playtest didn't exercise.

## Run summary

| Metric | Value |
|---|---|
| Turns played | **35** |
| Acts reached | **1 → 2 → 3 → 4** (10 / 10 / 12 / 4 turns each) |
| Errors | **0** |
| Pivots fired | **`act3_kira_disclosure_pivot`** at turn 30 |
| Foreshadow payoffs delivered | `hyperspace_signatures`, `kira_blade_stance`, `seren_denn_name` |
| Memorable moments captured | 7 |
| Threads tracked at end | 82 |
| Faction emergent shifts seen on | Jedi Praxeum, Imperial Remnant (Tannen's Task Force) |
| Side content engaged | `follow_kira_or_wait`, `perimeter_lantern_repair`, `tionne_archive_visit` |
| Median turn latency | ~15s (95th: ~28s, max: 32s on a milestone-adjacent turn) |

The session reached the Act 3 climax and continued into Act 4 cleanly.
No 429s during the run — the new Retry-After backoff was on the path
but didn't need to engage.

## Findings against the four follow-up questions

### 1. Did combat tactical state activate and advance through rounds?

**No** — but **negotiation tactical state did, repeatedly and well.**

The combat plan (turn 26 free-form: "If Tannen's task force breaches the
perimeter, position myself between the students and the breach…") did
not trigger a combat scene. The narrative chose to keep the Imperial
threat as off-screen pressure (TIE staging, hyperspace signatures,
imperial transponder taps) rather than drop the player into a
stormtrooper firefight. That's a defensible authorial call — the
investigative spine never put a body in front of the player to shoot
at — but it means the **combat tactical-state grammar is still
unverified at scale**.

What _did_ exercise tactical state: **negotiation**, fully and across
the rubric. The grammar advanced through the canonical stages
`opening → probing → pressure → give_or_break` and then cycled into
fresh negotiation sessions when scene types shifted (Tionne / Kira /
Malakai sequences each opened their own negotiation block).
Round counters reached 11 in the longest single negotiation. The system
correctly cleared and re-armed when scenes broke.

| Tactical kind | Sessions seen | Round high-water |
|---|---|---|
| `negotiation` | 4 distinct sessions | 11 (turn 18) |
| `combat` | 0 | 0 |
| `chase` | 0 | 0 |

**Recommendation:** the next stress test should _force_ a combat scene
— either an explicit Act 4/5 firefight in the spine, or a free-form
action that the GM can't reroute around (e.g. "draw the lightsaber and
charge the breaching squad"). Until then, combat tactical state is
verified by unit tests but not by live play.

### 2. Did `act3_kira_disclosure_pivot` fire — and did the prompt visibly land it?

**Yes — fired on turn 30, and the prompt landed it.**

`pivots_fired = ["act3_kira_disclosure_pivot"]`. The pivot warning
block (`_build_pivot_warning_block`) marked the turn weighty, and the
narration acted accordingly:

> _Turn 30:_ "You keep your voice level and pin Malakai with the
> question instead of the accusation behind it. 'Who is the package
> for?' His eyes stay on you. He does not look at Luke, and he does
> not look at Kira. That is answer enough to make the question…"

All four choices on turn 30 are pivot-shaped — naming the recipient,
sealing the stairs, watching the three lies — none of them is a
soft "ask a clarifying question" cosmetic. The pivot fired the
turn before its trigger threshold (act_progress 0.83) but had clearly
been building from turns 26–29, which is the desired ramp.

**No follow-up needed.** The pivot machinery is working.

### 3. Did contradiction-arc movements accumulate?

**No — `contradiction_arc.movements == 0` for all 35 turns.** This
is the predicted miss.

Verification: every snapshot has `contradiction_arc == {}`. The
reconciliation prompt block in
[engine/reconciliation.py:467](../../engine/reconciliation.py:467) does
load (the spine has `protagonist_contradiction` authored on both
character variants), but the model is consistently returning either
`contradiction_engaged: false` or `arc_movement: "none"`.

**Diagnosis: the prompt under-claims, and the schema lets the model
opt out.**

```
Was this contradiction relevant to what just happened? If yes:
- "reinforced": ...
- "resisted": ...
- "transformed": ...
- "cost_paid": ...
- "none": The contradiction wasn't relevant this turn.
```

Two issues:

1. **"If yes" framing invites a no.** The model defaults to
   conservative judgment — and a turn about "questioning Kira about the
   shuttle transponder" is _exactly_ the protagonist's contradiction
   ("believes knowledge should be shared freely, but instinctively
   hoards") in motion, but the prompt lets the model skip judgment.
2. **`arc_movement` enum allows `"none"`, and only `contradiction_engaged`
   is required.** So the model can return `{"contradiction_engaged": false}`
   and skip the arc_movement entirely — which is what's happening.

**Proposed calibration** (small, low-risk, in
[engine/reconciliation.py:467-473](../../engine/reconciliation.py:467)):

> Replace `"Was this contradiction relevant to what just happened? If
> yes:"` with: `"How did this turn relate to the contradiction? Pick
> one — even a subtle echo counts as 'reinforced' or 'resisted'.
> 'none' is reserved for turns with literally no relevance (e.g. pure
> mechanical exposition with no character action)."`

Plus tighten the schema: keep `arc_movement` optional but signal in
the description that "none" is the rare case, not the default. If
that's still too lax, lift `contradiction_engaged` out of the schema
entirely and infer it from `arc_movement != "none"`.

I'd propose landing this calibration as a **separate small commit**
once verified on a 5-turn sanity run — not folded into this stress
test commit. Risk: a recalibration that flips most turns to
`reinforced` would inflate the counts ledger and bias the
narration block toward over-emphasizing the contradiction. The 8-entry
cap in `accumulate_contradiction_arc` mitigates that, but the dominant-
movement surface in `build_contradiction_arc_block` could become
monotonous.

### 4. Did any memorable-moment callback surface in later passages?

**Heuristically: 1 detected. Substantively: weak.**

The callback detector flagged turn 34 as echoing the turn 33 moment
("You keep your voice even, and Malakai hears the edge under it
anyway"). On inspection, this is **the model self-quoting** — the
narration on turn 34 reuses the same beat structure rather than
genuinely calling back to a past moment from a fresh angle. The
detector did its job (≥2 distinctive tokens shared) but the underlying
narrative move is closer to repetition than callback.

What the detector missed (because tokens didn't overlap enough): the
**prayer-bead gesture** in the turn 35 free-form was a deliberate
callback to the protagonist's authored background ("the aunt gave the
protagonist three blank prayer beads") and the system surfaced it
naturally — but because it was the player's free-form action, not a
prior _generated_ moment, it doesn't count as a memorable-moment
callback in the strict sense.

**Conclusion:** The memorable-moments ledger is _populating_ correctly
(7 moments captured across 35 turns), but the **surface-side callback
mechanism** is producing weaker results than expected. Worth a closer
look in a future pass:

- The narration prompt asks the GM to seed callbacks "when natural,"
  which the model interprets conservatively.
- The act-3 → act-4 transition is exactly when callbacks should pay
  off, but only one self-quote landed in those 4 turns.

This isn't a fix-now bug; it's a quality observation for the next
narration-prompt iteration. Suggest tracking it as a soft follow-up.

## Star Wars fan readability and immersion notes

Read with the lens of a regular Star Wars fan (Bantam-era novels, OT
movies, Mandalorian, Squadrons) — not the tabletop FFG audience:

### What lands

- **Period hardware is correct and concrete.** "Imperial transponder,"
  "TIE and frigates in the same breath," "the system edge," "Massassi
  vault," "Praxeum," "patrol strip," "perimeter lantern" — all verbs
  and props that a fan recognizes without exposition. The narration
  earns its setting.
- **Praxeum-era voice is consistent.** Post-_Return of the Jedi_,
  pre-Yuuzhan Vong, Luke as quietly-experienced teacher, Tionne as
  archivist. No Skywalker-shouts, no Force-meditation purple. Reads
  like a careful Bantam-era novel.
- **Investigative pacing fits the Praxeum subgenre.** The opening 10
  turns are an evidence-gathering scene cycle — patrol logs,
  maintenance notes, missing signatures, a sealed stair. That's the
  exact register of _Children of the Jedi_, _The New Rebellion_,
  _I, Jedi_. A fan settles in.
- **Choices have voice.** The four choices each turn are not
  paraphrases of one another. They feel like _Keth_-shaped (or rather
  _the Praxeum Student_-shaped) decisions — patience vs. confrontation
  vs. evidence-first vs. one-clean-question. The "introspection"
  option doesn't preachify.
- **The pivot beats land cinematically.** Turn 20 ("You say Malakai's
  name into the narrow space under the bent hatch, and Kira stops
  moving. Her hand stays on the stone lip.") is the kind of beat that
  a fan would screenshot. No cape-billowing, no quote-the-prophecy.
- **Free-form actions get respected.** The prayer-bead gesture on turn
  35 — invented in the moment — became a load-bearing object the
  narration treated as canon ("the broken altar tile with a dry click,"
  "Kira's eyes cut to it once"). That's the exact loop that makes a
  player feel _seen_.

### What's a little off

- **Imperial threat stays diffuse.** Tannen's task force is referenced
  often (transponder, TIE staging, frigates) but never seen. For a
  Star Wars fan, _Stormtroopers in the corridor_ is an emotional beat
  that the engine can describe but never delivered in this 35-turn run.
  See the combat-tactical-state miss above.
- **The Force is well-handled but quiet.** "Reach for the Force…" /
  "feel for the truth around her answers" are present, but no
  set-piece Force moment landed (no saber draw, no telekinetic
  lift, no vergence vision). For a Force-tradition campaign the
  ratio of investigative beats to Force beats is investigation-heavy.
  This may be a feature (Praxeum-era _academic_ mysticism) but a fan
  would expect at least one charged Force scene by turn 20.
- **Self-quoting on turn 33→34.** A fan reading two consecutive
  turns and noticing the model literally repeated "you keep your voice
  even, and Malakai hears the edge under it" would feel the seam. Not
  fatal, but noticeable.
- **Choice prefixes occasionally break voice.** Choices like
  "Hold Malakai to his own answer and name the one thing he keeps
  dodging…" can over-describe the player's intent in ways that read
  more like a stage-direction than a thought. Minor — most choices
  read clean.

### What a fan would want next

- **One Force beat per act.** A vergence flash, a saber form
  recognition, a meditation that lands a vision. The engine has Force
  Sense / Influence in the toolset but the narration didn't reach for
  them in this run.
- **An on-screen Imperial.** Even a brief scene with a captured
  scout or an intercepted comm voice. Tannen as a name-on-a-frequency
  is fine for atmosphere but eventually a fan wants a face.
- **A Praxeum ritual or a cantina scene.** The only authored
  Praxeum-fixture references that landed are "Tionne's archive" and
  "the broken altar." Authored set pieces (a meal, a sparring circle,
  a stranger arriving) would give the fan a recognizable beat per act.

Overall: the prose **reads like a quiet Bantam-era Praxeum novel**.
That is exactly the era voice the spine targets. The depth pass made
the world feel less like a state machine and more like a place — the
crystallized memory ("Tionne measures the room before she speaks"),
the lore seeds, the side content (Tionne's archive, the lantern
repair) all surface naturally. A regular fan would say "I'd keep
playing this."

## Per-turn arc-state trace

| Turn | Act | Prog | Threads | Moments | Factions | Pivots | Tactical | Note |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0 | 1 | 0.00 | 0 | 0 | 0 | 0 | — | opening |
| 1 | 1 | 0.10 | 4 | 0 | 0 | 0 | — | |
| 2 | 1 | 0.20 | 5 | 0 | 0 | 0 | negotiation | |
| 3 | 1 | 0.30 | 7 | 0 | 1 | 0 | negotiation | |
| 4 | 1 | 0.40 | 9 | 0 | 1 | 0 | negotiation | |
| 5 | 1 | 0.50 | 13 | 1 | 1 | 0 | negotiation | first memorable moment |
| 6 | 1 | 0.60 | 15 | 1 | 1 | 0 | — | |
| 7 | 1 | 0.70 | 17 | 1 | 1 | 0 | — | |
| 8 | 1 | 0.80 | 19 | 1 | 1 | 0 | — | |
| 9 | 1 | 0.90 | 21 | 1 | 1 | 0 | negotiation | |
| 10 | 2 | 0.00 | 23 | 1 | 2 | 0 | negotiation | act boundary; Imperial faction surfaces |
| 11 | 2 | 0.10 | 30 | 1 | 2 | 0 | negotiation | |
| 12 | 2 | 0.20 | 30 | 1 | 2 | 0 | negotiation | |
| 13 | 2 | 0.30 | 35 | 2 | 2 | 0 | negotiation | |
| 14 | 2 | 0.40 | 37 | 2 | 2 | 0 | negotiation | |
| 15 | 2 | 0.50 | 39 | 2 | 2 | 0 | negotiation | |
| 16 | 2 | 0.60 | 41 | 2 | 2 | 0 | negotiation | |
| 17 | 2 | 0.70 | 41 | 3 | 2 | 0 | negotiation | descent into lower Massassi |
| 18 | 2 | 0.80 | 43 | 3 | 2 | 0 | negotiation | round 11 — long negotiation |
| 19 | 2 | 0.90 | 44 | 4 | 2 | 0 | — | |
| 20 | 3 | 0.00 | 46 | 4 | 2 | 0 | — | act boundary; "I know about Malakai" |
| 21 | 3 | 0.08 | 51 | 4 | 2 | 0 | negotiation | new negotiation session |
| 22 | 3 | 0.17 | 54 | 4 | 2 | 0 | negotiation | |
| 23 | 3 | 0.25 | 56 | 4 | 2 | 0 | negotiation | |
| 24 | 3 | 0.33 | 58 | 4 | 2 | 0 | negotiation | |
| 25 | 3 | 0.42 | 61 | 4 | 2 | 0 | — | |
| 26 | 3 | 0.50 | 63 | 4 | 2 | 0 | negotiation | combat-shaped free-form rerouted to negotiation |
| 27 | 3 | 0.58 | 64 | 4 | 2 | 0 | negotiation | |
| 28 | 3 | 0.67 | 68 | 5 | 2 | 0 | negotiation | |
| 29 | 3 | 0.75 | 70 | 5 | 2 | 0 | negotiation | |
| 30 | 3 | 0.83 | 72 | 5 | 2 | 1 | negotiation | **`act3_kira_disclosure_pivot` fires** |
| 31 | 3 | 0.92 | 74 | 5 | 2 | 1 | negotiation | |
| 32 | 4 | 0.00 | 77 | 5 | 2 | 1 | negotiation | act boundary into Act 4 |
| 33 | 4 | 0.08 | 78 | 6 | 2 | 1 | negotiation | |
| 34 | 4 | 0.17 | 81 | 6 | 2 | 1 | negotiation | self-quote callback |
| 35 | 4 | 0.25 | 82 | 7 | 2 | 1 | negotiation | prayer-bead gesture lands |

## Follow-ups proposed

1. **Recalibrate contradiction tracking** in
   [engine/reconciliation.py:467-473](../../engine/reconciliation.py:467) —
   reframe the prompt away from "if yes" and lean toward "subtle
   echoes count." Land as a small separate commit after a 5-turn
   verification run.
2. **Force a combat scene in the next stress test** so combat tactical
   state actually gets exercised end-to-end. Either author an explicit
   Act 4/5 firefight in the Shadows spine, or design a free-form
   action the GM can't reroute around.
3. **Investigate weak callback surfacing** as a soft follow-up — not a
   fix-now bug, but a quality lever for the next narration-prompt
   iteration. The ledger captures moments correctly; the call-back
   reach in narration is the part that's underdelivering.
4. **Kira-blade-stance and seren-denn-name foreshadow payoffs both
   delivered** — that's a solid result for the foreshadow registry
   runtime. Not a follow-up; a noted win.
