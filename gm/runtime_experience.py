"""
Phase 25 runtime experience helpers (runtime-experience-redesign spec).

Provides the deterministic logic that surfaces codex links, stakes,
set-piece treatments, foreshadowing payoffs, achievement progress, and
personality-axis annotations to the GM context and the API responses.

Pure functions, no LLM calls. Each helper is independently testable.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


# ── §2.1 Codex surface conditions ────────────────────────────────────


def select_available_codex_entries(
    spine: dict,
    *,
    current_act: int,
    present_npcs: list[str],
    location: str,
    flags: list[str] | None = None,
    max_count: int = 8,
) -> list[dict]:
    """Pick the codex entries whose surface conditions match this scene.

    The narration prompt includes these so the LLM can decide whether
    to surface 0-2 of them in the choice slot. Returns a list of dicts
    with entry_id, title, tag, and a short body excerpt.
    """
    flags = list(flags or [])
    out: list[dict] = []
    for entry in (spine.get("codex") or []):
        cond = entry.get("surface_when") or {}
        if cond.get("requires_act_minimum", 0) > current_act:
            continue
        req_npcs = cond.get("requires_npcs") or []
        if req_npcs and not any(name in present_npcs for name in req_npcs):
            continue
        req_locs = cond.get("requires_locations") or []
        if req_locs and not any(loc in (location or "") for loc in req_locs):
            continue
        req_flags = cond.get("requires_flags") or []
        if req_flags and not all(f in flags for f in req_flags):
            continue
        body = entry.get("body", "")
        excerpt = body[:240] + ("..." if len(body) > 240 else "")
        out.append({
            "entry_id": entry.get("entry_id", ""),
            "title": entry.get("title", ""),
            "tag": entry.get("tag", ""),
            "excerpt": excerpt,
        })
        if len(out) >= max_count:
            break
    return out


def build_codex_block(available_entries: list[dict]) -> str:
    """Render the AVAILABLE CODEX block for the narration prompt."""
    if not available_entries:
        return ""
    lines = [
        "AVAILABLE CODEX (Phase 25 §2.1 — surface 0-2 in choice slot when",
        "they would enrich the scene; format: '<title> [codex:<entry_id>]'):",
    ]
    for entry in available_entries:
        lines.append(
            f"  - {entry['title']} {entry['tag']} → "
            f"[codex:{entry['entry_id']}]"
        )
    return "\n".join(lines)


# ── §2.5/§2.6 Personality axis annotation ────────────────────────────


# Heuristic keyword → axis nudge map. The annotator uses these to bump
# personality axes based on the player's choice text. Conservative —
# small magnitude — so a single choice does not flip an axis.
AXIS_KEYWORD_MAP: list[tuple[str, list[str], int]] = [
    # (pair_id, keyword list, delta to pole_a_value)
    # Lone Wolf ↔ Crew Loyalist
    ("lone_wolf_crew_loyalist", ["alone", "by yourself", "without telling", "go solo"], +3),
    ("lone_wolf_crew_loyalist", ["with the crew", "together", "the team", "your friends", "trust", "ask for help"], -3),
    # Reckless ↔ Cautious
    ("reckless_cautious", ["charge", "rush", "leap", "throw yourself", "go in hot"], +3),
    ("reckless_cautious", ["wait", "hold back", "watch first", "consider", "careful"], -3),
    # Showy ↔ Quiet
    ("showy_quiet", ["announce", "draw attention", "loud", "make a scene", "showmanship"], +3),
    ("showy_quiet", ["slip", "quiet", "unseen", "without ceremony", "out of sight"], -3),
    # Direct ↔ Subtle
    ("direct_subtle", ["confront", "demand", "say it", "tell them straight", "head-on"], +3),
    ("direct_subtle", ["misdirect", "imply", "hint", "let them think", "back channel"], -3),
    # Lawful ↔ Lawless
    ("lawful_lawless", ["report", "follow orders", "by the book", "sanctioned", "permission"], +3),
    ("lawful_lawless", ["bend the rules", "ignore the law", "no permission", "smuggle", "backdoor"], -3),
]


def annotate_axis_movement(
    choice_text: str,
    *,
    visible_costs: list[dict] | None = None,
) -> list[tuple[str, int, str]]:
    """Inspect a player's choice text and visible_costs to derive axis movements.

    Returns a list of (pair_id, delta, cue_summary) tuples to apply to the
    character's personality_axes. Visible cost tags ("Morality: -3") are
    NOT applied here — those go through MotivationTrack.morality. This
    helper handles the five non-morality axes only.
    """
    movements: list[tuple[str, int, str]] = []
    if not choice_text:
        return movements
    text = choice_text.lower()
    used = set()
    for (pair_id, keywords, delta) in AXIS_KEYWORD_MAP:
        if pair_id in used:
            continue
        for kw in keywords:
            if kw in text:
                used.add(pair_id)
                cue = f"chose: {choice_text[:80]}"
                movements.append((pair_id, delta, cue))
                break
    return movements


def build_personality_axis_block(character) -> str:
    """Render the player's current axis state for the narration prompt."""
    axes = getattr(character, "personality_axes", None) or []
    if not axes:
        return ""
    lines = ["PERSONALITY AXES (Phase 25 §2.6 — reflect these in voice):"]
    for axis in axes:
        v = axis.pole_a_value
        if v >= 65:
            descriptor = f"strongly {axis.pole_a_label.lower()}"
        elif v >= 55:
            descriptor = f"leaning {axis.pole_a_label.lower()}"
        elif v <= 35:
            descriptor = f"strongly {axis.pole_b_label.lower()}"
        elif v <= 45:
            descriptor = f"leaning {axis.pole_b_label.lower()}"
        else:
            descriptor = "balanced"
        lines.append(
            f"  - {axis.pole_a_label} ↔ {axis.pole_b_label}: {v}/{100-v} — {descriptor}"
        )
    lines.append(
        "Let dominant axes color the protagonist's voice and the texture of "
        "small choices, without naming the labels."
    )
    return "\n".join(lines)


def build_personality_locks_block(character) -> str:
    """Render the player's locked beliefs for the narration prompt."""
    locks = getattr(character, "personality_locks", None) or []
    if not locks:
        return ""
    lines = ["ACTIVE BELIEF COMMITMENTS (Phase 25 §2.5 — protagonist holds these):"]
    for lock in locks:
        lines.append(f'  - "{lock.belief_text}"')
    lines.append(
        "These beliefs shape interpretation. Choices that contradict them "
        "should feel like effort or self-betrayal in the prose. The "
        "protagonist would not pick a contradicting choice lightly."
    )
    return "\n".join(lines)


# ── §2.8 Set-piece treatment ─────────────────────────────────────────


def lookup_set_piece(spine: dict, anchor_id: str) -> Optional[dict]:
    """Find a SetPieceDeclaration by anchor_id."""
    if not anchor_id:
        return None
    for sp in (spine.get("set_pieces") or []):
        if sp.get("anchor_id") == anchor_id:
            return sp
    return None


def build_set_piece_block(set_piece: dict | None) -> str:
    """Render the SET-PIECE block for the narration prompt."""
    if not set_piece:
        return ""
    multiplier = float(set_piece.get("word_budget_multiplier", 1.5))
    title = set_piece.get("scene_title", "")
    return (
        f"SET PIECE (Phase 25 §2.8): This scene is a designated peak moment.\n"
        f"  Title: {title}\n"
        f"  Word budget multiplier: {multiplier:.2f}x normal pacing target\n"
        f"  This is a moment that should feel different from routine scenes.\n"
        f"  Slow down. Land detail. The reader will remember this scene."
    )


def get_scene_treatment(spine: dict, anchor_id: str, stakes_level: str) -> dict | None:
    """Return scene_treatment dict for the API response (Phase 25 §2.8/§2.10)."""
    set_piece = lookup_set_piece(spine, anchor_id)
    if not set_piece and stakes_level not in ("high", "critical"):
        return None
    out = {
        "scene_title": set_piece.get("scene_title", "") if set_piece else "",
        "visual_treatment": (
            set_piece.get("visual_treatment", "scene_break")
            if set_piece else "none"
        ),
        "stakes_level": stakes_level or "normal",
        "epigraph": "",
    }
    return out


# ── §2.10 Stakes computation ─────────────────────────────────────────


def compute_stakes_level(
    *,
    is_set_piece: bool,
    is_personality_lock: bool,
    relationship_at_threshold: bool,
    achievement_imminent: bool,
    death_or_irreversible_risk: bool,
    is_climax: bool = False,
) -> str:
    """Decide low/normal/high/critical stakes for this turn."""
    if is_climax or death_or_irreversible_risk:
        return "critical"
    if is_set_piece or is_personality_lock or relationship_at_threshold:
        return "high"
    if achievement_imminent:
        return "high"
    return "normal"


def build_stakes_block(stakes_level: str) -> str:
    """Render the STAKES block for the narration prompt."""
    if stakes_level == "critical":
        return (
            "STAKES (Phase 25 §2.10): CRITICAL. Death or irreversible loss is on "
            "the table. The prose should slow down, deepen sensory detail, and "
            "let the reader feel the weight. Do not soften the moment."
        )
    if stakes_level == "high":
        return (
            "STAKES (Phase 25 §2.10): HIGH. This moment matters. The prose "
            "should land with intensity — not melodrama, but presence."
        )
    return ""


# ── §2.9 Lightweight foreshadowing ───────────────────────────────────


def select_foreshadowing(
    spine: dict,
    arc_state: dict,
    *,
    current_act: int,
) -> tuple[Optional[dict], str]:
    """Pick a lightweight foreshadowing entry to plant or pay off this turn.

    Returns (entry, kind) where kind is "plant" or "payoff" or "" when no
    entry applies. Uses the lighter Act.foreshadowing_plants list rather
    than the heavier ForeshadowLink registry (those go through CS-6).
    """
    delivered_plants = set(arc_state.get("light_foreshadow_plants_delivered", []) or [])
    delivered_payoffs = set(arc_state.get("light_foreshadow_payoffs_delivered", []) or [])
    acts = spine.get("acts") or []

    # Pass 1: payoff
    for act in acts:
        for entry in act.get("foreshadowing_plants") or []:
            key = f"{entry.get('plant_act',0)}-{entry.get('payoff_act',0)}-{entry.get('plant_concept','')[:40]}"
            if entry.get("payoff_act") == current_act and key in delivered_plants and key not in delivered_payoffs:
                return entry, "payoff"

    # Pass 2: plant
    for act in acts:
        for entry in act.get("foreshadowing_plants") or []:
            key = f"{entry.get('plant_act',0)}-{entry.get('payoff_act',0)}-{entry.get('plant_concept','')[:40]}"
            if entry.get("plant_act") == current_act and key not in delivered_plants:
                return entry, "plant"

    return None, ""


def build_light_foreshadow_block(entry: dict | None, kind: str) -> str:
    """Render the lightweight foreshadowing block for the narration prompt."""
    if not entry or not kind:
        return ""
    if kind == "plant":
        return (
            f"LIGHT FORESHADOWING — PLANT (Phase 25 §2.9): Optionally weave a "
            f"small detail or a line of dialogue that foreshadows this future "
            f"beat. Do not announce it. Make it feel natural and easy to miss.\n"
            f"  Plant: {entry.get('plant_concept','')}"
        )
    if kind == "payoff":
        return (
            f"LIGHT FORESHADOWING — PAYOFF (Phase 25 §2.9): An earlier setup "
            f"is ready to land. Reference it with recognition, not exposition.\n"
            f"  Setup was: {entry.get('plant_concept','')}\n"
            f"  Payoff is: {entry.get('payoff_concept','')}"
        )
    return ""


def mark_light_foreshadow_delivered(
    arc_state: dict, entry: dict, kind: str,
) -> None:
    """Update arc_state once the narration has surfaced a plant/payoff."""
    key = f"{entry.get('plant_act',0)}-{entry.get('payoff_act',0)}-{entry.get('plant_concept','')[:40]}"
    if kind == "plant":
        plants = arc_state.setdefault("light_foreshadow_plants_delivered", [])
        if key not in plants:
            plants.append(key)
    elif kind == "payoff":
        payoffs = arc_state.setdefault("light_foreshadow_payoffs_delivered", [])
        if key not in payoffs:
            payoffs.append(key)


# ── §2.7 Achievement engine ──────────────────────────────────────────


def evaluate_achievements(
    spine: dict,
    character,
    arc_state: dict,
    *,
    last_turn_event: dict | None = None,
) -> list[str]:
    """Check whether any achievements should be awarded this turn.

    Returns a list of newly-earned achievement_ids. Idempotent — already
    earned achievements are skipped.
    """
    earned_now: list[str] = []
    achievements = spine.get("achievements") or []
    already_earned = set(getattr(character, "achievements_earned", []) or [])
    last_turn_event = last_turn_event or {}

    for ach in achievements:
        ach_id = ach.get("achievement_id", "")
        if not ach_id or ach_id in already_earned:
            continue
        cond = ach.get("earn_condition") or {}
        ctype = cond.get("condition_type", "")
        params = cond.get("parameters") or {}
        if _condition_met(
            ctype, params, character, arc_state, last_turn_event,
        ):
            earned_now.append(ach_id)

    # Apply
    if earned_now:
        if not isinstance(character.achievements_earned, list):
            character.achievements_earned = []
        for ach_id in earned_now:
            if ach_id not in character.achievements_earned:
                character.achievements_earned.append(ach_id)
    return earned_now


def _condition_met(
    ctype: str,
    params: dict,
    character,
    arc_state: dict,
    last_turn_event: dict,
) -> bool:
    """Evaluate one earn condition. Conservative: silent fail on unknown types."""
    if ctype == "milestone":
        target_milestone = params.get("milestone_id", "")
        delivered = arc_state.get("milestones_reached", []) or []
        return target_milestone and target_milestone in delivered
    if ctype == "force_power_milestone":
        target_power = params.get("power_id", "")
        if not target_power:
            return False
        return any(
            (p.get("power_id") == target_power)
            for p in (getattr(character, "force_powers", None) or [])
        )
    if ctype == "spine_anchor":
        target_anchor = params.get("anchor_id", "")
        return (
            target_anchor
            and target_anchor in (arc_state.get("anchors_reached", []) or [])
        )
    if ctype == "codex":
        topic_tag = params.get("tag", "")
        required_count = int(params.get("required_count", 1))
        spine = arc_state.get("_spine_for_eval") or {}
        codex = spine.get("codex") or []
        topic_entries = [e for e in codex if e.get("tag") == topic_tag]
        if not topic_entries:
            return False
        read = set(getattr(character, "codex_read", []) or [])
        hit_count = sum(1 for e in topic_entries if e.get("entry_id") in read)
        return hit_count >= required_count
    if ctype == "relationship":
        target_npc = params.get("npc_name", "")
        threshold = float(params.get("disposition_minimum", 0.8))
        for state in arc_state.get("npc_states", []) or []:
            if state.get("name") == target_npc:
                return float(state.get("disposition", 0.5)) >= threshold
        return False
    if ctype == "pattern":
        # Generic counter — incremented externally via achievement_progress.
        target_id = params.get("achievement_id", "")
        target_count = int(params.get("count", 5))
        progress = getattr(character, "achievement_progress", {}) or {}
        return int(progress.get(target_id, 0)) >= target_count
    return False


def increment_achievement_progress(
    character,
    achievement_id: str,
    amount: int = 1,
) -> None:
    """Bump a progress counter for pattern-based achievements."""
    if not isinstance(character.achievement_progress, dict):
        character.achievement_progress = {}
    character.achievement_progress[achievement_id] = (
        int(character.achievement_progress.get(achievement_id, 0)) + amount
    )


# ── §3.2 Goal-priming detection ─────────────────────────────────────


def should_emit_goal_priming(
    *,
    is_act_close: bool,
    is_personality_lock_close: bool,
    is_prologue_close: bool,
) -> bool:
    """Return True when this turn should end with a goal-priming line."""
    return bool(is_act_close or is_personality_lock_close or is_prologue_close)


def build_goal_priming_block(reason: str) -> str:
    """Render the goal-priming instruction for the narration prompt."""
    if not reason:
        return ""
    return (
        f"GOAL PRIMING (Phase 25 §3.2 — {reason}): Close the passage with a "
        f"single line of narrator-voice goal-priming. The line should name "
        f"what the protagonist wants going forward in a way the player will "
        f"remember. Examples: 'Your training begins now.' / 'You will find "
        f"them. Whatever it takes.' Do not preface; let it be the final beat."
    )


# ── §3.7 Recap card on session resume ───────────────────────────────


def build_recap(arc_state: dict, recent_turns: list, last_turn) -> dict | None:
    """Build a compact recap dict for sessions returning after a break."""
    if not recent_turns:
        return None
    summary_lines = []
    for t in recent_turns[-2:]:
        line = f"Turn {t.turn_number}: {t.player_action}"
        if t.dice_result:
            line += f" — {t.dice_result}"
        summary_lines.append(line)
    summary = "; ".join(summary_lines)

    act_summary = ""
    summaries = arc_state.get("act_summaries") or []
    if summaries:
        act_summary = summaries[-1].get("summary", "") if isinstance(summaries[-1], dict) else str(summaries[-1])
    return {
        "summary": summary[:500],
        "act_summary": act_summary[:600] if act_summary else "",
    }


# ── §2.5 Personality-lock moment detection ─────────────────────────


def find_personality_lock_for_anchor(spine: dict, anchor_id: str) -> dict | None:
    """Look up a PersonalityLockMoment by anchor_id."""
    if not anchor_id:
        return None
    for moment in (spine.get("personality_lock_moments") or []):
        if moment.get("anchor_id") == anchor_id:
            return moment
    return None


def build_personality_lock_block(moment: dict | None) -> str:
    """Render the PERSONALITY LOCK MOMENT block for narration."""
    if not moment:
        return ""
    options_lines = []
    for option in moment.get("belief_options") or []:
        options_lines.append(f"  - \"{option.get('belief_text', '')}\"")
    options_text = "\n".join(options_lines)
    return (
        f"PERSONALITY LOCK MOMENT (Phase 25 §2.5): This scene is a belief "
        f"commitment moment. The choices on this turn must be these belief "
        f"statements (each a multi-clause statement the player signs onto). "
        f"The chosen belief will shape future narration.\n"
        f"  Prompt: {moment.get('prompt_text', '')}\n"
        f"  Options:\n{options_text}\n"
        f"Render the prose so it ends at the moment of decision; the choices "
        f"are the belief statements verbatim."
    )
