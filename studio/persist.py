"""
Spine persistence (Phase 4).

The Campaign Studio's generators return spine dicts but never write them to
disk. The Game Engine's load_campaign_spine() reads data/campaigns/{slug}.json.
This module bridges the two: slugify a campaign name the same way the loader
normalizes it, then write the spine to that path collision-safely.

Pure filesystem + JSON; no LLM, no DB.
"""

import json
from pathlib import Path

CAMPAIGNS_DIR = Path("data/campaigns")


def slugify_campaign(name: str) -> str:
    """Normalize a campaign name to its on-disk slug.

    Mirrors api.game_routes.load_campaign_spine: lowercase, spaces -> '_',
    strip a leading 'the_'. Non-alphanumeric runs collapse to single '_'.
    """
    import re

    slug = str(name or "").strip().lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]+", "_", slug).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if slug.startswith("the_"):
        slug = slug[4:]
    return slug or "campaign"


def write_spine(spine: dict, *, overwrite: bool = False) -> str:
    """Write a spine dict to data/campaigns/{slug}.json and return the slug.

    The slug is derived from spine['name']. When a file already exists and
    overwrite is False, a numeric suffix (_2, _3, ...) is appended so a
    freshly generated campaign never clobbers an existing one. The returned
    slug is exactly what should be passed to POST /session as campaign_name.
    """
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
    base = slugify_campaign(spine.get("name", "campaign"))

    slug = base
    if not overwrite:
        n = 2
        while (CAMPAIGNS_DIR / f"{slug}.json").exists():
            slug = f"{base}_{n}"
            n += 1

    path = CAMPAIGNS_DIR / f"{slug}.json"
    path.write_text(
        json.dumps(spine, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return slug
