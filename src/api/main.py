"""
src/api/main.py - FastAPI application entry point
Chay: uvicorn src.api.main:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# React build output (frontend/vite.config.ts -> outDir: "../dist")
DIST_DIR = Path(__file__).resolve().parents[3] / "dist"

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khoi tao SQLChain khi server start - load schema vao cache."""
    from src.chain.sql_chain import SQLChain
    from src.llm.client import validate_llm_config

    logger.info("Starting up - validating config...")
    validate_llm_config()
    logger.info("Initializing SQLChain...")
    app.state.chain = SQLChain()
    logger.info("Server ready.")
    yield
    logger.info("Shutting down.")
    app.state.chain = None


app = FastAPI(
    title="Northwind SQL Chatbot",
    description=(
        "Chatbot noi bo (B2E) - hoi dap bang tieng Viet, "
        "tu dong sinh SQL va tra loi tu Northwind Database"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

from src.api.routes import router

app.include_router(router, prefix="/api/v1")


@app.get("/", response_class=HTMLResponse, tags=["root"])
async def root():
    index = DIST_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text())
    return HTMLResponse(
        "<h2>Frontend not built. Run: cd frontend && npm run build</h2>",
        status_code=503,
    )


# Serve React static assets -- must be after all API routes
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")
