"""
Knowledge Base API
Endpoints for managing role-skill mappings in training data CSV
"""
import csv
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
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
    """Response containing all role mappings"""
    mappings: List[RoleMapping]
    count: int
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

@router.get("/mappings", response_model=MappingsResponse)
async def get_mappings():
    """
    Get all role-skill mappings from training data.
    
    Returns a list of all role-skill mappings defined in the 
    training data CSV file.
    """
    mappings = read_csv_mappings()
    
    return MappingsResponse(
        mappings=mappings,
        count=len(mappings),
        source_file=str(DEFAULT_CSV_FILE.name)
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
