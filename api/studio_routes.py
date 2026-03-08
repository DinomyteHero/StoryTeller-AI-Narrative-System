"""
Campaign Studio API routes — Modes 3, 2, and 1, plus cross-era import.

Routes:
- POST /studio/spine/validate     — Validate a spine (partial or complete)
- POST /studio/spine/gaps         — Identify structural gaps
- POST /studio/spine/finalize     — Parse, validate, and finalize a spine
- POST /studio/assist/context     — Generate galactic context for an act
- POST /studio/assist/voice       — Generate NPC voice notes
- POST /studio/generate/mode2     — Generate spine from thematic brief
- POST /studio/generate/mode1     — Generate spine from minimal input
- POST /studio/generate/saga      — Run full saga pipeline
- POST /studio/import/apply       — Apply import interface to character
- POST /studio/import/default     — Build default character from variant
- GET  /studio/campaigns          — List stored campaigns
- POST /studio/campaigns          — Store a validated campaign spine
- GET  /studio/campaigns/{id}     — Retrieve a stored campaign spine
"""

from __future__ import annotations

import json
import uuid
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from studio.schema import CampaignSpine
from studio.validate import validate_spine
from studio.generate import (
    identify_gaps,
    generate_galactic_context,
    generate_npc_voice_notes,
    finalize_spine,
    validate_and_report,
    generate_from_brief,
    generate_mode1,
    ThematicBrief,
    Mode1Input,
)
from studio.import_interface import (
    ImportPackage,
    apply_import,
    build_default_character,
)
from studio.seeding import generate_master_seed
from studio.saga.pipeline import run_saga_pipeline
from state.db import get_connection


router = APIRouter(prefix="/studio", tags=["studio"])


# ── Request/Response Models ───────────────────────────────────────────


class ValidateRequest(BaseModel):
    spine_data: dict


class GapsRequest(BaseModel):
    spine_data: dict


class FinalizeRequest(BaseModel):
    spine_data: dict
    master_seed: Optional[int] = None
    model_used: str = ""


class ContextRequest(BaseModel):
    spine_data: dict
    act_number: int
    master_seed: Optional[int] = None


class VoiceRequest(BaseModel):
    npc_data: dict
    era: str
    location: str = ""
    master_seed: Optional[int] = None


class Mode2GenerateRequest(BaseModel):
    era: str
    location: str
    tone: str
    throughline_question: str
    campaign_concept: str
    moral_register: str = "morally gray"
    total_acts: int = 4
    constraints: str = ""
    master_seed: Optional[int] = None


class ImportApplyRequest(BaseModel):
    import_package: dict
    spine_data: dict
    variant_id: str


class ImportDefaultRequest(BaseModel):
    spine_data: dict
    variant_id: str


class Mode1GenerateRequest(BaseModel):
    era: str
    location: str
    tone: str = "gritty"
    moral_register: str = "morally gray"
    negative_archetype: str = "Generic hero's journey with clear good/evil binary"
    archetype_avoidance: str = "Avoid redemption arcs that resolve cleanly"
    master_seed: Optional[int] = None


class SagaPipelineRequest(BaseModel):
    era: str
    location: str
    tone: str = "gritty"
    moral_register: str = "morally gray"
    num_directions: int = Field(default=3, ge=2, le=6)
    prior_campaign_json: Optional[dict] = None
    master_seed: Optional[int] = None


class StoreCampaignRequest(BaseModel):
    spine_data: dict
    authoring_mode: str = "mode3"
    prior_campaign_id: Optional[str] = None


# ── Validation & Gap Routes ──────────────────────────────────────────


@router.post("/spine/validate")
async def validate_spine_route(req: ValidateRequest):
    """Validate a campaign spine and return the full report.

    Accepts partial spines for early feedback, but only complete spines
    will pass all gates.
    """
    try:
        report = validate_and_report(req.spine_data)
        return report.to_dict()
    except ValueError as e:
        return {
            "passed": False,
            "errors": [{"gate": 0, "code": "parse_error", "message": str(e), "path": ""}],
            "warnings": [],
            "gates_passed": [],
            "difficulty_curve": None,
        }


@router.post("/spine/gaps")
async def identify_gaps_route(req: GapsRequest):
    """Identify structural gaps in a partially-built spine.

    Pure Python analysis — no LLM calls. Useful during Mode 3 authoring
    to catch missing fields and structural issues before validation.
    """
    gaps = identify_gaps(req.spine_data)
    return {"gaps": gaps, "total": len(gaps)}


@router.post("/spine/finalize")
async def finalize_spine_route(req: FinalizeRequest):
    """Parse, attach metadata, validate, and finalize a campaign spine.

    This is the final step of Mode 3 workflow. Returns the validated
    spine as JSON plus the validation report.
    """
    try:
        spine, report = finalize_spine(
            req.spine_data,
            master_seed=req.master_seed,
            model_used=req.model_used,
        )
        return {
            "spine": spine.model_dump(mode="json"),
            "validation_report": report.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── AI Assistance Routes ─────────────────────────────────────────────


@router.post("/assist/context")
async def assist_galactic_context(req: ContextRequest):
    """Generate galactic context draft for a specific act.

    The author provides the act structure; the AI drafts the wider
    galactic context. The author reviews and edits the result.
    """
    try:
        context = generate_galactic_context(
            req.spine_data,
            req.act_number,
            master_seed=req.master_seed,
        )
        return {"act_number": req.act_number, "galactic_context": context}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")


@router.post("/assist/voice")
async def assist_npc_voice(req: VoiceRequest):
    """Generate voice notes for an NPC.

    Describes HOW the character speaks — speech patterns, verbal habits,
    emotional register. The author reviews and edits the result.
    """
    try:
        voice_notes = generate_npc_voice_notes(
            req.npc_data,
            req.era,
            req.location,
            master_seed=req.master_seed,
        )
        return {
            "npc_name": req.npc_data.get("name", "Unknown"),
            "voice_notes": voice_notes,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")


# ── Mode 2 Generation Routes ─────────────────────────────────────────


@router.post("/generate/mode2")
async def generate_mode2(req: Mode2GenerateRequest):
    """Generate a complete campaign spine from a thematic brief.

    Mode 2: AI generates the entire spine from thematic direction.
    The author reviews and edits the result before finalizing.
    """
    brief = ThematicBrief(
        era=req.era,
        location=req.location,
        tone=req.tone,
        throughline_question=req.throughline_question,
        campaign_concept=req.campaign_concept,
        moral_register=req.moral_register,
        total_acts=req.total_acts,
        constraints=req.constraints,
    )
    try:
        spine_data, master_seed = generate_from_brief(
            brief, master_seed=req.master_seed,
        )
        # Run gap analysis on the generated spine
        gaps = identify_gaps(spine_data)
        return {
            "spine_data": spine_data,
            "master_seed": master_seed,
            "gaps": gaps,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Mode 1 Generation Routes ────────────────────────────────────────


@router.post("/generate/mode1")
async def generate_mode1_route(req: Mode1GenerateRequest):
    """Generate a complete campaign spine from minimal input.

    Mode 1: Fully autonomous. Provide era, location, tone, and moral
    register — the AI generates everything else.
    """
    inputs = Mode1Input(
        era=req.era,
        location=req.location,
        tone=req.tone,
        moral_register=req.moral_register,
        negative_archetype=req.negative_archetype,
        archetype_avoidance=req.archetype_avoidance,
    )
    try:
        spine_data, master_seed = generate_mode1(
            inputs, master_seed=req.master_seed,
        )
        gaps = identify_gaps(spine_data)
        return {
            "spine_data": spine_data,
            "master_seed": master_seed,
            "gaps": gaps,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Saga Pipeline Route ────────────────────────────────────────────


@router.post("/generate/saga")
async def generate_saga_route(req: SagaPipelineRequest):
    """Run the full 5-stage saga pipeline.

    The Writer's Room pipeline: persona assignment, divergent generation,
    branching search, convergent debate, and pairwise evaluation.

    Requires a prior campaign spine as input — the saga pipeline generates
    sequel campaigns building on previous narrative state.
    """
    if req.prior_campaign_json is None:
        raise HTTPException(
            status_code=400,
            detail="Saga pipeline requires prior_campaign_json",
        )
    try:
        result = run_saga_pipeline(
            req.prior_campaign_json,
            master_seed=req.master_seed,
        )
        return {
            "selected_spine": result.selected_spine,
            "all_candidates": result.all_candidates,
            "master_seed": result.master_seed,
            "directions_generated": result.directions_generated,
            "sketches_generated": result.sketches_generated,
            "drafts_generated": result.drafts_generated,
            "passed_validation": result.passed_validation,
            "validation_report": result.validation_report,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Cross-Era Import Routes ──────────────────────────────────────────


@router.post("/import/apply")
async def apply_import_route(req: ImportApplyRequest):
    """Apply import interface to transfer a character to a new campaign.

    Takes a character's import package and the receiving spine, returns
    the assembled character data for the Game Engine.
    """
    try:
        spine = CampaignSpine(**req.spine_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid spine: {e}")

    try:
        package = ImportPackage.from_dict(req.import_package)
        result = apply_import(package, spine, req.variant_id)
        return {
            "character_data": result.character_data,
            "applied_mappings": result.applied_mappings,
            "warnings": result.warnings,
            "xp_adjusted": result.xp_adjusted,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/default")
async def build_default_route(req: ImportDefaultRequest):
    """Build a default character from a variant (no import).

    For players starting fresh. Returns character data indistinguishable
    from a new start.
    """
    try:
        spine = CampaignSpine(**req.spine_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid spine: {e}")

    try:
        char_data = build_default_character(spine, req.variant_id)
        return {"character_data": char_data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Campaign Storage Routes ──────────────────────────────────────────


def _init_studio_tables():
    """Create Campaign Studio tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                era TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                authoring_mode TEXT NOT NULL,
                spine_json TEXT NOT NULL,
                validation_report TEXT,
                prior_campaign_id TEXT,
                FOREIGN KEY (prior_campaign_id) REFERENCES campaigns(id)
            );
        """)
        conn.commit()


@router.post("/campaigns")
async def store_campaign(req: StoreCampaignRequest):
    """Store a validated campaign spine.

    The spine is validated before storage — a spine that fails validation
    is rejected.
    """
    # Validate first
    try:
        spine = CampaignSpine(**req.spine_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid spine: {e}")

    report = validate_spine(spine)
    if not report.passed:
        error_msgs = "; ".join(e.message for e in report.errors)
        raise HTTPException(
            status_code=422,
            detail=f"Spine failed validation: {error_msgs}",
        )

    campaign_id = str(uuid.uuid4())
    _init_studio_tables()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO campaigns (id, name, era, authoring_mode, spine_json,
               validation_report, prior_campaign_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                campaign_id,
                spine.name,
                spine.era,
                req.authoring_mode,
                json.dumps(spine.model_dump(mode="json")),
                json.dumps(report.to_dict()),
                req.prior_campaign_id,
            ),
        )
        conn.commit()

    return {"campaign_id": campaign_id, "name": spine.name, "era": spine.era}


@router.get("/campaigns")
async def list_campaigns():
    """List all stored campaigns."""
    _init_studio_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, era, created_at, authoring_mode FROM campaigns ORDER BY created_at DESC"
        ).fetchall()
        return {
            "campaigns": [
                {
                    "id": row[0],
                    "name": row[1],
                    "era": row[2],
                    "created_at": row[3],
                    "authoring_mode": row[4],
                }
                for row in rows
            ]
        }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Retrieve a stored campaign spine by ID."""
    _init_studio_tables()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, era, created_at, authoring_mode, spine_json, validation_report FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    return {
        "id": row[0],
        "name": row[1],
        "era": row[2],
        "created_at": row[3],
        "authoring_mode": row[4],
        "spine": json.loads(row[5]),
        "validation_report": json.loads(row[6]) if row[6] else None,
    }
