"""
Vector refresh API endpoint.
"""

import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.similarity import get_search_engine, refresh_search_engine

logger = logging.getLogger(__name__)

router = APIRouter()


class RefreshResponse(BaseModel):
    """Response model for vector refresh."""
    status: str
    skills_indexed: int
    duration_seconds: float
    message: str


@router.post(
    "/skills/refresh-vectors",
    response_model=RefreshResponse,
    summary="Refresh skill vectors",
    description="Re-fetches skills from database and rebuilds all vectors"
)
async def refresh_vectors() -> RefreshResponse:
    """
    Refresh skill vectors from the database.
    
    This endpoint:
    1. Fetches all active skills (curatal_skill = 1) from database
    2. Generates new embeddings for all skills
    3. Saves vectors to disk
    4. Atomically swaps in-memory vectors
    
    The operation is thread-safe and does not require service restart.
    Existing requests continue using old vectors until swap is complete.
    
    Returns:
        Status information including number of skills indexed
    """
    engine = get_search_engine()
    
    if not engine.is_initialized:
        raise HTTPException(
            status_code=503,
            detail="Service not ready. Wait for initial initialization."
        )
    
    try:
        start_time = time.time()
        
        logger.info("Starting vector refresh via API")
        skills_count = refresh_search_engine()
        
        duration = time.time() - start_time
        
        logger.info(
            f"Vector refresh completed: {skills_count} skills in {duration:.2f}s"
        )
        
        return RefreshResponse(
            status="success",
            skills_indexed=skills_count,
            duration_seconds=round(duration, 2),
            message=f"Successfully refreshed {skills_count} skill vectors"
        )
        
    except ConnectionError as e:
        logger.error(f"Database connection failed during refresh: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Please try again later."
        )
    except RuntimeError as e:
        logger.error(f"Runtime error during refresh: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh vectors: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during refresh: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during refresh"
        )


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    skills_loaded: int
    initialized: bool


@router.get(
    "/skills/health",
    response_model=HealthResponse,
    summary="Check skill service health",
    description="Returns the current state of the skill search engine"
)
async def health_check() -> HealthResponse:
    """
    Check the health of the skill suggestion service.
    
    Returns:
        Current initialization state and number of indexed skills
    """
    engine = get_search_engine()
    
    return HealthResponse(
        status="healthy" if engine.is_initialized else "initializing",
        skills_loaded=engine.skill_count,
        initialized=engine.is_initialized
    )
