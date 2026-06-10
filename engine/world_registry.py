"""
World registry — validation gate for LLM-proposed narrative state.

The physics-before-imagination invariant covers dice, XP, and character
attributes, but narrative state (locations, known facts, NPC knowledge)
historically entered persistent state directly from LLM output. This module
is the gate: nothing enters the world ledger unless it is grounded in
canon (the campaign spine), in previously established state, or in prose
the player actually read.

Two validation surfaces:

1. Locations — a proposed `current_location` must share vocabulary with
   the spine's authored geography, an already-visited location, or the
   delivered passage itself. Accepted locations are recorded in
   `arc_state["visited_locations"]` with provenance (turn, source), so the
   world can grow — but only through an auditable append, never by drift.

2. Facts — a proposed fact (state-patch `known_facts`, reconciliation
   `knowledge_gained`) must share enough significant tokens with the source
   narration to be considered grounded. Ungrounded facts are dropped and
   logged; they never reach persistent state.

Pure Python. Zero LLM dependencies (Critical Rule 3).
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

VISITED_LOCATIONS_KEY = "visited_locations"
MAX_VISITED_LOCATIONS = 30

# Words too common to count as evidence that two location strings or a
# fact and its source text refer to the same thing.
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "from",
    "with", "near", "into", "onto", "under", "over", "above", "below",
    "beneath", "behind", "beside", "between", "through", "toward", "towards",
    "their", "your", "his", "her", "its", "this", "that", "these", "those",
    "where", "which", "while", "after", "before", "during", "again",
    "player", "character", "scene", "area", "place", "side", "edge",
    "you", "are", "is", "was", "were", "has", "have", "had", "will",
    "not", "now", "still", "just", "very", "what", "who", "how", "why",
    "they", "them", "there", "here", "about", "against", "around",
})

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def significant_tokens(text: str) -> set[str]:
    """Lowercased content tokens of a string, minus stopwords and noise."""
    if not text:
        return set()
    tokens = _TOKEN_RE.findall(text.lower())
    return {
        tok.strip("'") for tok in tokens
        if len(tok) >= 4 and tok not in _STOPWORDS
    }


def _tokens_match(a: str, b: str) -> bool:
    """Exact match or shared ≥4-char prefix — tolerates light morphology
    (call/calls/calling, feel/feels) without a stemmer dependency."""
    if a == b:
        return True
    return (len(a) >= 4 and b.startswith(a)) or (len(b) >= 4 and a.startswith(b))


def _overlap_count(needles: set[str], haystack: set[str]) -> int:
    return sum(
        1 for n in needles
        if any(_tokens_match(n, h) for h in haystack)
    )


# ── Locations ────────────────────────────────────────────────────────


def _authored_act_locations(act: dict) -> list[str]:
    """Location strings an act authors: opening_location plus the optional
    per-act location_vocabulary list."""
    locations: list[str] = []
    opening = act.get("opening_location", "")
    if isinstance(opening, str) and opening.strip():
        locations.append(opening)
    raw_vocab = act.get("location_vocabulary", [])
    if isinstance(raw_vocab, list):
        locations.extend(
            entry for entry in raw_vocab
            if isinstance(entry, str) and entry.strip()
        )
    return locations


def location_vocabulary(spine: Optional[dict], arc_state: Optional[dict]) -> set[str]:
    """Significant tokens of every location the world has established:
    authored act geography (opening locations + per-act location_vocabulary)
    plus the visited-location ledger."""
    vocab: set[str] = set()

    for act in (spine or {}).get("acts", []) or []:
        if isinstance(act, dict):
            for location in _authored_act_locations(act):
                vocab |= significant_tokens(location)
            vocab |= significant_tokens(act.get("name", ""))

    for entry in (arc_state or {}).get(VISITED_LOCATIONS_KEY, []) or []:
        if isinstance(entry, dict):
            vocab |= significant_tokens(entry.get("name", ""))
        elif isinstance(entry, str):
            vocab |= significant_tokens(entry)

    return vocab


def npc_location_domains(spine: Optional[dict]) -> dict[str, frozenset[str]]:
    """Per-NPC location domain tokens authored in the spine's npc_roster.

    Returns lowercase NPC name → frozen set of lowercase location tokens
    ("praxeum", "yavin", "off-world"; "*" = anywhere). NPCs without
    authored domains are absent — the runtime treats them as unconstrained.
    """
    domains: dict[str, frozenset[str]] = {}
    for npc in (spine or {}).get("npc_roster", []) or []:
        if not isinstance(npc, dict):
            continue
        name = str(npc.get("name") or "").strip().lower()
        raw = npc.get("location_domains")
        if not name or not isinstance(raw, list):
            continue
        tokens = frozenset(
            str(token).strip().lower()
            for token in raw
            if isinstance(token, (str, int)) and str(token).strip()
        )
        if tokens:
            domains[name] = tokens
    return domains


def match_location_from_text(
    text: str,
    spine: Optional[dict],
    current_act: Optional[dict] = None,
) -> str:
    """Best authored location named by a passage of text, or "".

    Candidates come from the current act's authored locations first, then
    the rest of the spine's acts. A candidate matches when every one of
    its significant tokens appears in the text; among matches the most
    token-specific wins. This is what lets scene-location inference work
    for ANY campaign rather than only hand-coded keyword tables.
    """
    text_tokens = significant_tokens(text)
    if not text_tokens:
        return ""

    candidates: list[str] = []
    if isinstance(current_act, dict):
        candidates.extend(_authored_act_locations(current_act))
    for act in (spine or {}).get("acts", []) or []:
        if isinstance(act, dict) and act is not current_act:
            candidates.extend(_authored_act_locations(act))

    best, best_size = "", 0
    for candidate in candidates:
        tokens = significant_tokens(candidate)
        if not tokens or len(tokens) <= best_size:
            continue
        if _overlap_count(tokens, text_tokens) == len(tokens):
            best, best_size = candidate, len(tokens)
    return best


def validate_proposed_location(
    proposed: str,
    *,
    spine: Optional[dict],
    arc_state: Optional[dict],
    prior_location: str = "",
    passage_text: str = "",
) -> tuple[bool, str]:
    """Decide whether an LLM-proposed location may enter persistent state.

    Accepted when the proposal shares vocabulary with:
      - the authored/visited world (spine geography + visited ledger), or
      - the prior location (refinement of where we already are), or
      - the delivered passage (the place was named in prose the player
        read — grounded growth rather than silent teleportation).

    Returns (accepted, source) where source is "canon", "prior",
    "narration", or "" when rejected.
    """
    tokens = significant_tokens(proposed)
    if not tokens:
        return False, ""

    if _overlap_count(tokens, location_vocabulary(spine, arc_state)) >= 1:
        return True, "canon"

    if _overlap_count(tokens, significant_tokens(prior_location)) >= 1:
        return True, "prior"

    # New ground: every content token of the place name must appear in the
    # passage. A place can be born here, but only if the prose actually
    # named it — not from the state patch alone.
    passage_tokens = significant_tokens(passage_text)
    if passage_tokens and _overlap_count(tokens, passage_tokens) == len(tokens):
        return True, "narration"

    return False, ""


def record_location(
    arc_state: dict,
    location: str,
    *,
    turn_number: int,
    source: str,
) -> None:
    """Append an accepted location to the visited-location ledger.

    Idempotent per location name. The ledger is provenance: which turn
    established this place and on what authority.
    """
    if not location:
        return
    ledger = arc_state.setdefault(VISITED_LOCATIONS_KEY, [])
    for entry in ledger:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if isinstance(name, str) and name.strip().lower() == location.strip().lower():
            return
    ledger.append({"name": location, "turn": turn_number, "source": source})
    if len(ledger) > MAX_VISITED_LOCATIONS:
        del ledger[:len(ledger) - MAX_VISITED_LOCATIONS]


# ── Facts ────────────────────────────────────────────────────────────


def ground_facts(
    facts: Iterable[str],
    source_text: str,
    *,
    min_ratio: float = 0.5,
    label: str = "fact",
) -> tuple[list[str], list[str]]:
    """Split proposed facts into (grounded, dropped) against a source text.

    A fact is grounded when at least `min_ratio` of its significant tokens
    appear in the source — i.e. the narration the player actually read
    contains the substance of the claim. Hallucinated facts ("the Emperor
    is alive on Jakku") share almost no content tokens with the passage
    and are dropped.

    Facts with no significant tokens (too short/generic to verify) are
    dropped: a fact that can't be checked can't enter the ledger.
    """
    source_tokens = significant_tokens(source_text)
    grounded: list[str] = []
    dropped: list[str] = []

    for fact in facts:
        if not isinstance(fact, str) or not fact.strip():
            continue
        tokens = significant_tokens(fact)
        if not tokens:
            dropped.append(fact)
            continue
        overlap = _overlap_count(tokens, source_tokens)
        if overlap / len(tokens) >= min_ratio:
            grounded.append(fact)
        else:
            dropped.append(fact)

    if dropped:
        logger.warning(
            "Dropped %d ungrounded %s(s) (not supported by narration): %s",
            len(dropped), label,
            "; ".join(f[:80] for f in dropped[:5]),
        )
    return grounded, dropped
