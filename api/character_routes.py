"""
Character creator HTTP routes (Phase 3).

POST /character/draft  — prose pitch -> LLM-drafted, editable stat block.
POST /character/save   — (edited) draft -> validated Character written to disk.
GET  /character/{id}   — load a saved character for re-editing.

The draft is intentionally returned un-assembled so the player can edit it in
the UI. assemble_character() (deterministic, mechanical-validity gate) runs at
save time, not draft time.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.ratelimit import SlidingWindowLimiter, client_key, limit_from_env
from engine.character import Character
from gm.character_creator import (
    draft_character, assemble_character, CharacterDraftError, _slugify,
)
from state.telemetry import funnel_event

log = logging.getLogger(__name__)
router = APIRouter()

CHARACTERS_DIR = Path("data/characters")

DRAFT_LIMITER = SlidingWindowLimiter(
    limit_from_env("FUNNEL_DRAFT_LIMIT_PER_HOUR", 30)
)


class DraftRequest(BaseModel):
    pitch: str = Field(min_length=1, max_length=2000)
    hints: Optional[dict] = None


class SaveRequest(BaseModel):
    character_json: dict


@router.post("/character/draft")
async def draft_route(req: DraftRequest, request: Request):
    """Draft a character from a prose pitch. ~8-15s (one FAST-tier LLM call)."""
    if not DRAFT_LIMITER.allow(client_key(request)):
        raise HTTPException(
            429,
            "You've drafted a lot of characters in the last hour — "
            "give the holotable a short rest and try again soon.",
        )
    started = time.monotonic()
    try:
        draft = draft_character(req.pitch, req.hints)
    except CharacterDraftError as e:
        funnel_event(
            "character_draft", ok=False,
            duration_s=round(time.monotonic() - started, 2),
        )
        raise HTTPException(422, {"errors": e.errors})
    except RuntimeError as e:
        # gm.llm_client raises RuntimeError on model/transport failure.
        funnel_event(
            "character_draft", ok=False,
            duration_s=round(time.monotonic() - started, 2),
        )
        raise HTTPException(502, f"Character draft failed: {e}")
    funnel_event(
        "character_draft", ok=True,
        duration_s=round(time.monotonic() - started, 2),
    )
    return {"draft": draft}


@router.post("/character/save")
async def save_route(req: SaveRequest):
    """Assemble + validate an (edited) draft, then write it to disk.

    Returns {character_id} on success. 422 with {errors} if the draft fails the
    mechanical-validity gate (e.g. a malformed signature talent).
    """
    try:
        character = assemble_character(req.character_json)
    except CharacterDraftError as e:
        raise HTTPException(422, {"errors": e.errors})
    except Exception as e:  # pydantic ValidationError et al.
        raise HTTPException(422, {"errors": [str(e)]})

    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    base = _slugify(character.name)
    slug = base
    n = 2
    while (CHARACTERS_DIR / f"{slug}.json").exists():
        slug = f"{base}_{n}"
        n += 1

    path = CHARACTERS_DIR / f"{slug}.json"
    path.write_text(character.model_dump_json(indent=2), encoding="utf-8")
    log.info("character_creator: saved %s", slug)
    funnel_event("character_save", character_id=slug)
    return {"character_id": slug, "name": character.name}


@router.get("/character/{character_id}")
async def get_character_route(character_id: str):
    """Load a saved character (for re-editing)."""
    path = CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Character not found: {character_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        Character.model_validate(data)  # integrity check
    except Exception as e:
        raise HTTPException(422, f"Invalid character file: {e}")
    return {"character_id": character_id, "character_json": data}
