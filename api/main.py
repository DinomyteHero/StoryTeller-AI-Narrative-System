"""
FastAPI application — Game Engine + Campaign Studio API.

Game Engine routes serve the player-facing game loop.
Campaign Studio routes serve the author-facing spine authoring workflow.
"""

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.game_routes import router as game_router
from api.studio_routes import router as studio_router
from api.character_routes import router as character_router
from state.db import init_db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup. Safe to call repeatedly."""
    init_db()
    yield


app = FastAPI(
    title="Storyteller V3",
    description="LLM-powered Star Wars narrative RPG engine",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the single-file frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount game routes
app.include_router(game_router)

# Mount studio routes
app.include_router(studio_router)

# Mount character-creator routes
app.include_router(character_router)


@app.get("/health")
async def health():
    """Health check + LLM routing summary.

    Confirms the engine is up and surfaces the active fast/quality tier
    models so deployments can verify the architecture pivot is live without
    hitting an actual LLM.
    """
    from gm.llm_client import describe_routing
    return {"status": "ok", "routing": describe_routing()}


@app.get("/")
async def root():
    """Serve the single-file frontend."""
    return FileResponse(WEB_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
