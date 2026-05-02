"""
src/api/main.py - FastAPI application entry point
Chay: uvicorn src.api.main:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.ui import render_app

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


@app.get("/", tags=["root"])
async def root():
    return render_app()
