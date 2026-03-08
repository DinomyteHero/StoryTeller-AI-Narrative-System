"""
Campaign Studio API routes — Mode 3 collaborative authoring.

Routes:
- POST /studio/spine/validate     — Validate a spine (partial or complete)
- POST /studio/spine/gaps         — Identify structural gaps
- POST /studio/spine/finalize     — Parse, validate, and finalize a spine
- POST /studio/assist/context     — Generate galactic context for an act
- POST /studio/assist/voice       — Generate NPC voice notes
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
)
from studio.seeding import generate_master_seed
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
