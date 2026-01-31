"""
Skill Suggestion Service - Main Application

A semantic skill suggestion service that:
- Accepts a job role/designation as input
- Suggests relevant skills using vector similarity
- Reads skills from PostgreSQL (read-only)
- Builds vectors at startup and on explicit refresh
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from api.suggest import router as suggest_router
from api.refresh import router as refresh_router
from core.similarity import initialize_search_engine

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initializes skill vectors on startup.
    """
    logger.info("Starting Skill Suggestion Service")
    
    # Validate required environment variables
    required_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise RuntimeError(f"Missing environment variables: {missing_vars}")
    
    # Initialize search engine (loads or builds vectors)
    try:
        initialize_search_engine()
        logger.info("Skill search engine initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize search engine: {e}")
        raise RuntimeError(f"Initialization failed: {e}")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down Skill Suggestion Service")


# Create FastAPI application
app = FastAPI(
    title="Skill Suggestion Service",
    description="""
    A semantic skill suggestion service using vector similarity.
    
    ## Features
    
    - **Skill Suggestion**: Given a job role, suggests relevant skills using semantic similarity
    - **Vector Refresh**: Rebuild skill vectors from database without service restart
    - **Health Check**: Monitor service status and initialization state
    
    ## How it works
    
    1. Skills are loaded from PostgreSQL (only active skills where curatal_skill = 1)
    2. Each skill name is converted to a vector embedding using sentence-transformers
    3. When a role is queried, it's normalized and embedded
    4. Cosine similarity finds the most relevant skills
    5. Results above threshold (0.45) are returned
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(suggest_router, tags=["Suggestions"])
app.include_router(refresh_router, tags=["Management"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Skill Suggestion Service",
        "version": "1.0.0",
        "endpoints": {
            "suggest_skills": "POST /suggest-skills",
            "refresh_vectors": "POST /skills/refresh-vectors",
            "health": "GET /skills/health",
            "docs": "GET /docs"
        }
    }
