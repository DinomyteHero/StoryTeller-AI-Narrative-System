"""
Choice tag classification and parsing (Phase 25 §2.2).

Two tag categories with different display treatment:

1. **Hidden hint tags**: skill names like [Deception], [Athletics] that
   indicate which check might fire. STRIPPED before display.
2. **Visible cost tags**: deterministic mechanical costs like
   [Force commit: 1], [Strain: 2], [Morality: -3], [Obligation: +5].
   RETAINED in display for the player to weigh.

A tag is "visible cost" if it has a deterministic numeric effect, the
effect is on a state the player can see in the dashboard, and the effect
is meaningful (>=1 unit).
"""

from dataclasses import dataclass, field
import re
from typing import Optional


# Visible cost tag prefixes — case-insensitive match. The colon is required
# to distinguish from skill tags (which never include a number).
VISIBLE_COST_TAG_PREFIXES = (
    "force commit",
    "force_commit",
    "strain",
    "wounds",
    "morality",
    "obligation",
    "duty",
    "conflict",
    "destiny",
)

# Codex link tags — surfaced as italic sideways navigation.
CODEX_LINK_TAG_PREFIXES = (
    "codex",
    "codex_link",
)


@dataclass
class ChoiceCost:
    """One parsed visible cost on a choice (e.g., 'Strain: 2')."""
    label: str   # e.g., "Strain", "Force commit", "Morality"
    value: int   # signed integer; positive = gain, negative = loss


@dataclass
class ChoiceTagInfo:
    """The structured tag content extracted from a choice line.

    A choice can carry at most one skill_tag (hidden) and any number of
    visible_costs (kept) and one codex_link (kept, marks the choice as
    sideways navigation rather than action).
    """
    skill_tag:    Optional[str] = None         # raw skill name, kept hidden
    visible_costs: list[ChoiceCost] = field(default_factory=list)
    codex_link:   Optional[str] = None         # codex entry_id when this is a sideways link


_COST_NUMBER_RE = re.compile(r"^([+\-]?\d+)$")


def _is_visible_cost_tag(text: str) -> Optional[ChoiceCost]:
    """Detect [Label: <number>] patterns that should remain visible."""
    if ":" not in text:
        return None
    label_part, _, value_part = text.partition(":")
    label = label_part.strip()
    value = value_part.strip()
    label_lower = label.lower().replace("_", " ")

    if not any(label_lower == prefix.replace("_", " ") for prefix in VISIBLE_COST_TAG_PREFIXES):
        return None
    match = _COST_NUMBER_RE.match(value)
    if not match:
        return None
    try:
        return ChoiceCost(label=label, value=int(match.group(1)))
    except ValueError:
        return None


def _is_codex_link_tag(text: str) -> Optional[str]:
    """Detect [codex:entry_id] tags. Returns the entry_id when matched."""
    lower = text.strip().lower()
    if not (lower.startswith("codex:") or lower.startswith("codex_link:")):
        return None
    _, _, entry_id = text.partition(":")
    entry_id = entry_id.strip()
    return entry_id or None


def _classify_tag(raw_tag: str) -> tuple[str, ChoiceTagInfo]:
    """Classify a single bracket-tag content. Returns (category, info-fragment).

    category is one of:
      - "visible_cost" — kept for display
      - "codex_link"   — marks choice as sideways navigation
      - "skill"        — stripped from display
    """
    info = ChoiceTagInfo()
    cost = _is_visible_cost_tag(raw_tag)
    if cost is not None:
        info.visible_costs.append(cost)
        return "visible_cost", info
    codex = _is_codex_link_tag(raw_tag)
    if codex is not None:
        info.codex_link = codex
        return "codex_link", info
    info.skill_tag = raw_tag.strip()
    return "skill", info


_TAG_RE = re.compile(r"\[([^\[\]]+)\]")


def parse_choice_tags(choice_text: str) -> tuple[str, ChoiceTagInfo]:
    """Extract tags from a choice line.

    Returns (display_text, tag_info). The display_text has skill tags
    stripped but visible cost tags retained inline. Codex link tags are
    stripped from display (the codex_link itself is on tag_info).
    """
    info = ChoiceTagInfo()
    out_parts: list[str] = []
    last_end = 0

    for match in _TAG_RE.finditer(choice_text):
        # text before this tag
        out_parts.append(choice_text[last_end:match.start()])
        category, fragment = _classify_tag(match.group(1))
        if category == "visible_cost":
            # Re-render the tag so the player sees it inline. Use the
            # canonical bracket form.
            cost = fragment.visible_costs[0]
            sign = "+" if cost.value > 0 else ""
            out_parts.append(f"[{cost.label}: {sign}{cost.value}]")
            info.visible_costs.extend(fragment.visible_costs)
        elif category == "codex_link":
            # Codex link — strip the tag from display; mark the choice.
            info.codex_link = fragment.codex_link
            # we strip even leading whitespace before the tag for cleaner display
        elif category == "skill":
            # Hidden skill tag — store first one, drop rest.
            if info.skill_tag is None:
                info.skill_tag = fragment.skill_tag
        last_end = match.end()

    out_parts.append(choice_text[last_end:])
    display = "".join(out_parts)
    # Tighten any double-spaces left behind by stripping a tag mid-line.
    display = re.sub(r"\s{2,}", " ", display).strip()
    # Remove orphan punctuation/spaces left at end
    display = re.sub(r"\s+([.,;:!?])", r"\1", display)
    return display, info


def format_costs_inline(costs: list[ChoiceCost]) -> str:
    """Join cost tags into a single trailing string, e.g. '[Strain: 2] [Force commit: 1]'."""
    if not costs:
        return ""
    parts = []
    for cost in costs:
        sign = "+" if cost.value > 0 else ""
        parts.append(f"[{cost.label}: {sign}{cost.value}]")
    return " ".join(parts)
