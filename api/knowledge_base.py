"""
Knowledge Base API
Endpoints for managing role-skill mappings in training data CSV
"""
import csv
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.role_mapper import reload_role_mapper

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])

# Training data path
TRAINING_DATA_DIR = Path(__file__).parent.parent / "training_data"
DEFAULT_CSV_FILE = TRAINING_DATA_DIR / "role_skills.csv"


# ============================================
# Pydantic Models
# ============================================

class RoleMapping(BaseModel):
    """A single role-skill mapping"""
    role: str
    skills: List[str]


class MappingsResponse(BaseModel):
    """Response containing role mappings (paginated)"""
    mappings: List[RoleMapping]
    count: int  # number of items on this page
    total: int  # total number of mappings
    page: int
    page_size: int
    source_file: str


class AddMappingRequest(BaseModel):
    """Request to add a new role mapping"""
    role: str = Field(..., min_length=1, max_length=500)
    skills: List[str] = Field(..., min_length=1)


class UpdateMappingRequest(BaseModel):
    """Request to update an existing role mapping"""
    original_role: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1, max_length=500)
    skills: List[str] = Field(..., min_length=1)


class MappingActionResponse(BaseModel):
    """Response for mapping actions"""
    success: bool
    message: str


# ============================================
# Helper Functions
# ============================================

def read_csv_mappings(filepath: Path = DEFAULT_CSV_FILE) -> List[RoleMapping]:
    """
    Read role-skill mappings from CSV file.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        List of RoleMapping objects
    """
    mappings = []
    
    if not filepath.exists():
        return mappings
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                role = row.get('role', '').strip()
                skills_str = row.get('skills', '')
                
                if role:
                    skills = [s.strip() for s in skills_str.split(',') if s.strip()]
                    mappings.append(RoleMapping(role=role, skills=skills))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read CSV file: {str(e)}"
        )
    
    return mappings


def write_csv_mappings(mappings: List[RoleMapping], filepath: Path = DEFAULT_CSV_FILE) -> None:
    """
    Write role-skill mappings to CSV file.
    
    Args:
        mappings: List of RoleMapping objects
        filepath: Path to CSV file
    """
    try:
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first, then rename for atomicity
        temp_path = filepath.with_suffix('.csv.tmp')
        
        with open(temp_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['role', 'skills'])
            
            for mapping in mappings:
                skills_str = ','.join(mapping.skills)
                writer.writerow([mapping.role, skills_str])
        
        # Atomic rename
        if filepath.exists():
            filepath.unlink()
        temp_path.rename(filepath)
        
    except Exception as e:
        # Cleanup temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write CSV file: {str(e)}"
        )


# ============================================
# API Endpoints
# ============================================

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def filter_mappings_by_search(mappings: List[RoleMapping], search: str) -> List[RoleMapping]:
    """
    Filter mappings where the search term appears in role or in any skill (case-insensitive).
    """
    if not search or not search.strip():
        return mappings
    term = search.strip().lower()
    return [
        m
        for m in mappings
        if term in m.role.lower()
        or any(term in s.lower() for s in m.skills)
    ]


@router.get("/mappings", response_model=MappingsResponse)
async def get_mappings(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search by role or skill name (case-insensitive)"),
):
    """
    Get role-skill mappings from training data with server-side pagination and optional search.

    Use `search` to filter by role or skill name. Use `page` and `page_size` to navigate.
    """
    all_mappings = read_csv_mappings()
    if search:
        all_mappings = filter_mappings_by_search(all_mappings, search)
    total = len(all_mappings)

    start = (page - 1) * page_size
    end = start + page_size
    page_mappings = all_mappings[start:end]

    return MappingsResponse(
        mappings=page_mappings,
        count=len(page_mappings),
        total=total,
        page=page,
        page_size=page_size,
        source_file=str(DEFAULT_CSV_FILE.name),
    )


@router.post("/mappings", response_model=MappingActionResponse)
async def add_mapping(request: AddMappingRequest):
    """
    Add a new role-skill mapping.
    
    Appends a new role-skill mapping to the training data CSV.
    Reloads the role mapper after adding.
    """
    mappings = read_csv_mappings()
    
    # Check for duplicate role
    existing_roles = {m.role.lower() for m in mappings}
    if request.role.lower() in existing_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role '{request.role}' already exists"
        )
    
    # Add new mapping
    new_mapping = RoleMapping(
        role=request.role.strip(),
        skills=[s.strip() for s in request.skills if s.strip()]
    )
    mappings.append(new_mapping)
    
    # Write back
    write_csv_mappings(mappings)
    
    # Reload role mapper
    try:
        reload_role_mapper()
    except Exception as e:
        print(f"Warning: Failed to reload role mapper: {e}")
    
    return MappingActionResponse(
        success=True,
        message=f"Successfully added mapping for '{request.role}'"
    )


@router.put("/mappings", response_model=MappingActionResponse)
async def update_mapping(request: UpdateMappingRequest):
    """
    Update an existing role-skill mapping.
    
    Updates the role and/or skills for an existing mapping.
    Reloads the role mapper after updating.
    """
    mappings = read_csv_mappings()
    
    # Find the mapping to update
    found_index = None
    for i, m in enumerate(mappings):
        if m.role.lower() == request.original_role.lower():
            found_index = i
            break
    
    if found_index is None:
        raise HTTPException(
            status_code=404,
            detail=f"Role '{request.original_role}' not found"
        )
    
    # If role name is changing, check for conflicts
    if request.role.lower() != request.original_role.lower():
        existing_roles = {m.role.lower() for j, m in enumerate(mappings) if j != found_index}
        if request.role.lower() in existing_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{request.role}' already exists"
            )
    
    # Update mapping
    mappings[found_index] = RoleMapping(
        role=request.role.strip(),
        skills=[s.strip() for s in request.skills if s.strip()]
    )
    
    # Write back
    write_csv_mappings(mappings)
    
    # Reload role mapper
    try:
        reload_role_mapper()
    except Exception as e:
        print(f"Warning: Failed to reload role mapper: {e}")
    
    return MappingActionResponse(
        success=True,
        message=f"Successfully updated mapping for '{request.role}'"
    )


@router.delete("/mappings/{role}", response_model=MappingActionResponse)
async def delete_mapping(role: str):
    """
    Delete a role-skill mapping.
    
    Removes the specified role from the training data CSV.
    Reloads the role mapper after deleting.
    """
    mappings = read_csv_mappings()
    
    # Find and remove the mapping
    initial_count = len(mappings)
    mappings = [m for m in mappings if m.role.lower() != role.lower()]
    
    if len(mappings) == initial_count:
        raise HTTPException(
            status_code=404,
            detail=f"Role '{role}' not found"
        )
    
    # Write back
    write_csv_mappings(mappings)
    
    # Reload role mapper
    try:
        reload_role_mapper()
    except Exception as e:
        print(f"Warning: Failed to reload role mapper: {e}")
    
    return MappingActionResponse(
        success=True,
        message=f"Successfully deleted mapping for '{role}'"
    )
