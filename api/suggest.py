"""
Skill suggestion API endpoint.
Supports hybrid search: role mapping + semantic fallback.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from core.similarity import get_search_engine, SkillMatch

logger = logging.getLogger(__name__)

router = APIRouter()


class SuggestRequest(BaseModel):
    """Request model for skill suggestion."""
    role: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Job role or designation to find skills for"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of skills to return"
    )
    use_mapping: bool = Field(
        default=True,
        description="Use role-skill mappings from training data if available"
    )
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate and clean role input."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Role cannot be empty or whitespace only")
        return cleaned


class SkillResponse(BaseModel):
    """Response model for a single skill."""
    skill_id: int
    skill_name: str
    confidence: float
    source: Optional[str] = None  # "mapped" or "semantic"


class SuggestResponse(BaseModel):
    """Response model for skill suggestion."""
    normalized_role: str
    skills: List[SkillResponse]
    search_method: str  # "mapped", "hybrid", or "semantic"


@router.post(
    "/suggest-skills",
    response_model=SuggestResponse,
    summary="Suggest skills for a job role",
    description="Returns relevant skills using hybrid search: role mapping + semantic similarity"
)
async def suggest_skills(request: SuggestRequest) -> SuggestResponse:
    """
    Suggest relevant skills for a given job role.
    
    Uses hybrid search:
    1. Check if role matches training data mappings (e.g., "MERN Stack" -> MongoDB, React...)
    2. If mapping found, return those skills from database
    3. If no mapping or partial results, supplement with semantic search
    
    Args:
        request: Contains role, limit, and use_mapping flag
        
    Returns:
        Normalized role, matching skills, and search method used
    """
    engine = get_search_engine()
    
    if not engine.is_initialized:
        raise HTTPException(
            status_code=503,
            detail="Service not ready. Skill vectors not yet initialized."
        )
    
    try:
        normalized_role, matches, search_method = engine.hybrid_search(
            role=request.role,
            limit=request.limit,
            use_role_mapping=request.use_mapping
        )
        
        skills = [
            SkillResponse(
                skill_id=match.skill_id,
                skill_name=match.skill_name,
                confidence=match.confidence,
                source=match.source
            )
            for match in matches
        ]
        
        logger.info(
            f"Suggested {len(skills)} skills for role '{request.role}' "
            f"(normalized: '{normalized_role}', method: {search_method})"
        )
        
        return SuggestResponse(
            normalized_role=normalized_role,
            skills=skills,
            search_method=search_method
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error in suggest_skills: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
