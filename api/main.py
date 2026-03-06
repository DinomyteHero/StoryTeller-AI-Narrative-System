"""
FastAPI application — Game Engine API.

Three working routes. Full loop accessible via HTTP.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.game_routes import router as game_router
from state.db import init_db

app = FastAPI(
    title="Storyteller V3",
    description="LLM-powered Star Wars narrative RPG engine",
    version="0.1.0",
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


@app.on_event("startup")
def startup():
    """Initialize database on startup. Safe to call repeatedly."""
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
