"""
Skill suggestion API endpoint.
"""

import logging
from typing import List

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


class SuggestResponse(BaseModel):
    """Response model for skill suggestion."""
    normalized_role: str
    skills: List[SkillResponse]


@router.post(
    "/suggest-skills",
    response_model=SuggestResponse,
    summary="Suggest skills for a job role",
    description="Returns a list of relevant skills based on semantic similarity to the provided role"
)
async def suggest_skills(request: SuggestRequest) -> SuggestResponse:
    """
    Suggest relevant skills for a given job role.
    
    Processing steps:
    1. Normalize the role text (lowercase, remove noise words)
    2. Generate embedding for normalized role
    3. Compute cosine similarity against all skill vectors
    4. Return top-N skills above similarity threshold
    
    Args:
        request: Contains role and optional limit
        
    Returns:
        Normalized role and list of matching skills with confidence scores
    """
    engine = get_search_engine()
    
    if not engine.is_initialized:
        raise HTTPException(
            status_code=503,
            detail="Service not ready. Skill vectors not yet initialized."
        )
    
    try:
        normalized_role, matches = engine.search(
            role=request.role,
            limit=request.limit
        )
        
        skills = [
            SkillResponse(
                skill_id=match.skill_id,
                skill_name=match.skill_name,
                confidence=match.confidence
            )
            for match in matches
        ]
        
        logger.info(
            f"Suggested {len(skills)} skills for role '{request.role}' "
            f"(normalized: '{normalized_role}')"
        )
        
        return SuggestResponse(
            normalized_role=normalized_role,
            skills=skills
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error in suggest_skills: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
