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
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine.character import Character
from gm.character_creator import (
    draft_character, assemble_character, CharacterDraftError, _slugify,
)

log = logging.getLogger(__name__)
router = APIRouter()

CHARACTERS_DIR = Path("data/characters")


class DraftRequest(BaseModel):
    pitch: str = Field(min_length=1, max_length=2000)
    hints: Optional[dict] = None


class SaveRequest(BaseModel):
    character_json: dict


@router.post("/character/draft")
async def draft_route(req: DraftRequest):
    """Draft a character from a prose pitch. ~8-15s (one FAST-tier LLM call)."""
    try:
        draft = draft_character(req.pitch, req.hints)
    except CharacterDraftError as e:
        raise HTTPException(422, {"errors": e.errors})
    except RuntimeError as e:
        # gm.llm_client raises RuntimeError on model/transport failure.
        raise HTTPException(502, f"Character draft failed: {e}")
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
