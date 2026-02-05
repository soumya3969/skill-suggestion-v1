"""
Training API endpoints.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from core.trainer import (
    train_model,
    TrainingConfig,
    trained_model_exists,
    delete_trained_model,
    TRAINING_DATA_DIR,
    DEFAULT_TRAINING_FILE,
    TRAINED_MODEL_PATH,
)
from core.similarity import refresh_search_engine, get_search_engine, unload_model
from core.role_mapper import reload_role_mapper, get_role_mapper

logger = logging.getLogger(__name__)

router = APIRouter()


class TrainRequest(BaseModel):
    """Request model for training."""
    training_file: Optional[str] = Field(
        default=None,
        description="Name of training CSV file in training_data/ folder (default: role_skills.csv)"
    )
    epochs: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of training epochs"
    )
    batch_size: int = Field(
        default=16,
        ge=2,
        le=128,
        description="Training batch size"
    )


class TrainResponse(BaseModel):
    """Response model for training."""
    model_config = {"protected_namespaces": ()}
    
    success: bool
    model_path: str
    training_pairs: int
    epochs: int
    message: str


class ModelStatusResponse(BaseModel):
    """Response model for model status."""
    model_config = {"protected_namespaces": ()}
    
    trained_model_exists: bool
    model_path: str
    skills_indexed: int
    using_trained_model: bool
    role_mappings_loaded: int


@router.post(
    "/model/train",
    response_model=TrainResponse,
    summary="Train skill suggestion model",
    description="Fine-tune the model on role-skill pairs from CSV training data/n/nTraining data format (CSV):/nrole,skills/n\"MERN Stack Developer\",\"MongoDB,Express.js,React.js,Node.js\"/n\"Data Scientist\",\"Python,Machine Learning,Pandas,NumPy,SQL,TensorFlow\""
)
async def train_skill_model(request: TrainRequest) -> TrainResponse:
    """
    Train the skill suggestion model on labeled data.
    
    This endpoint:
    1. Loads role-skill pairs from CSV
    2. Fine-tunes sentence-transformer using contrastive learning
    3. Saves the trained model locally
    4. Automatically refreshes skill vectors with new model
    
    Training data format (CSV):
        role,skills
        "MERN Stack Developer","MongoDB,Express.js,React.js,Node.js"
    """
    # Determine training file path
    if request.training_file:
        training_file = TRAINING_DATA_DIR / request.training_file
    else:
        training_file = DEFAULT_TRAINING_FILE
    
    if not training_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Training file not found: {training_file.name}. "
                   f"Place CSV files in training_data/ folder."
        )
    
    # Configure training
    config = TrainingConfig(
        epochs=request.epochs,
        batch_size=request.batch_size
    )
    
    logger.info(f"Starting model training from {training_file}")
    
    try:
        # Unload existing model to release file handles (Windows fix)
        logger.info("Unloading existing model from memory")
        unload_model()
        
        # Train the model
        result = train_model(training_file=training_file, config=config)
        
        if result.success:
            # Refresh vectors with the new model
            logger.info("Refreshing skill vectors with trained model")
            refresh_search_engine()
            
            # Reload role mapper to use the same training data for direct mappings
            logger.info("Reloading role mapper with training data")
            reload_role_mapper(training_file)
        
        return TrainResponse(
            success=result.success,
            model_path=result.model_path,
            training_pairs=result.training_pairs,
            epochs=result.epochs,
            message=result.message
        )
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Training failed: {str(e)}"
        )


@router.post(
    "/model/upload-training-data",
    summary="Upload training data CSV",
    description="Upload a CSV file with role-skill training pairs"
)
async def upload_training_data(
    file: UploadFile = File(..., description="CSV file with role,skills columns"),
    filename: Optional[str] = Form(default=None, description="Custom filename (optional)")
):
    """
    Upload a training data CSV file.
    
    The CSV should have two columns:
    - role: The job role/designation
    - skills: Comma-separated list of associated skills
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are accepted"
        )
    
    # Determine save path
    save_filename = filename if filename else file.filename
    if not save_filename.endswith('.csv'):
        save_filename += '.csv'
    
    save_path = TRAINING_DATA_DIR / save_filename
    
    # Ensure directory exists
    TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        # Read and validate content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Basic validation - check headers
        lines = content_str.strip().split('\n')
        if not lines:
            raise HTTPException(status_code=400, detail="Empty CSV file")
        
        header = lines[0].lower()
        if 'role' not in header or 'skills' not in header:
            raise HTTPException(
                status_code=400,
                detail="CSV must have 'role' and 'skills' columns"
            )
        
        # Save file
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content_str)
        
        return {
            "success": True,
            "filename": save_filename,
            "path": str(save_path),
            "rows": len(lines) - 1,  # Exclude header
            "message": f"Training data saved. Use POST /model/train to start training."
        }
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file encoding. Please use UTF-8."
        )
    except Exception as e:
        logger.error(f"Failed to save training data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save training data: {str(e)}"
        )


@router.get(
    "/model/status",
    response_model=ModelStatusResponse,
    summary="Get model status",
    description="Check if a trained model exists and is being used"
)
async def get_model_status() -> ModelStatusResponse:
    """
    Get the current status of the skill suggestion model.
    """
    engine = get_search_engine()
    mapper = get_role_mapper()
    model_exists = trained_model_exists()
    
    return ModelStatusResponse(
        trained_model_exists=model_exists,
        model_path=str(TRAINED_MODEL_PATH) if model_exists else "Using base model: all-MiniLM-L6-v2",
        skills_indexed=engine.skill_count,
        using_trained_model=model_exists,
        role_mappings_loaded=mapper.role_count
    )


@router.delete(
    "/model/trained",
    summary="Delete trained model",
    description="Remove the trained model and revert to base model"
)
async def remove_trained_model():
    """
    Delete the trained model to revert to the base sentence-transformer model.
    """
    if not trained_model_exists():
        return {
            "success": True,
            "message": "No trained model exists. Already using base model."
        }
    
    try:
        delete_trained_model()
        
        # Refresh vectors with base model
        logger.info("Refreshing skill vectors with base model")
        refresh_search_engine()
        
        return {
            "success": True,
            "message": "Trained model deleted. Reverted to base model. Vectors refreshed."
        }
        
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete model: {str(e)}"
        )


@router.get(
    "/model/training-files",
    summary="List training data files",
    description="List available training data CSV files"
)
async def list_training_files():
    """
    List all CSV files in the training_data directory.
    """
    TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    csv_files = list(TRAINING_DATA_DIR.glob("*.csv"))
    
    files = []
    for f in csv_files:
        # Count rows
        try:
            with open(f, 'r', encoding='utf-8') as file:
                row_count = sum(1 for _ in file) - 1  # Exclude header
        except:
            row_count = -1
        
        files.append({
            "filename": f.name,
            "rows": row_count,
            "is_default": f.name == "role_skills.csv"
        })
    
    return {
        "training_data_directory": str(TRAINING_DATA_DIR),
        "files": files
    }
