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
from api.train import router as train_router
from api.knowledge_base import router as kb_router
from core.similarity import initialize_search_engine, refresh_search_engine
from core.role_mapper import initialize_role_mapper
from core.trainer import trained_model_exists, train_model, DEFAULT_TRAINING_FILE

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
    
    # Initialize role mapper (loads training data for direct mappings)
    try:
        role_count = initialize_role_mapper()
        logger.info(f"Role mapper initialized with {role_count} role mappings")
    except Exception as e:
        logger.warning(f"Role mapper initialization failed (non-critical): {e}")
    
    # Auto-train model if trained model is missing but training data exists
    try:
        if not trained_model_exists():
            if DEFAULT_TRAINING_FILE.exists():
                logger.info("Trained model not found but training data exists - starting automatic training")
                result = train_model()
                if result.success:
                    logger.info(f"Auto-training complete: {result.message}")
                    # Refresh vectors to use the newly trained model
                    logger.info("Refreshing vectors with newly trained model")
                    refresh_search_engine()
                    logger.info("Vectors refreshed with trained model embeddings")
                else:
                    logger.warning(f"Auto-training failed: {result.message}")
                    logger.info("Continuing with base model")
            else:
                logger.info("Trained model not found and no training data available - using base model")
        else:
            logger.info("Trained model found - using trained model for embeddings")
    except Exception as e:
        logger.warning(f"Auto-training failed (non-critical): {e}")
        logger.info("Continuing with base model")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down Skill Suggestion Service")


# OpenAPI tags metadata for better documentation organization
tags_metadata = [
    {
        "name": "Suggestions",
        "description": "Skill suggestion endpoints. Get relevant skills for job roles.",
    },
    {
        "name": "Management",
        "description": "Service management endpoints. Health checks and vector refresh.",
    },
    {
        "name": "Training",
        "description": "Model training endpoints. Train custom models on role-skill mappings.",
    },
    {
        "name": "Knowledge Base",
        "description": "Manage role-skill mappings in the training data CSV file.",
    },
    {
        "name": "Root",
        "description": "Service information and status.",
    },
]

# Create FastAPI application
app = FastAPI(
    title="Skill Suggestion Service",
    description="""
        ## Overview

        A semantic skill suggestion service using vector similarity with trainable model.

        ## Features

        - **Skill Suggestion**: Given a job role, suggests relevant skills using semantic similarity
        - **Model Training**: Fine-tune the model on role-skill pairs for better associations
        - **Vector Refresh**: Rebuild skill vectors from database without service restart
        - **Health Check**: Monitor service status and initialization state

        ## How it works

        1. Skills are loaded from PostgreSQL (only active skills where `curatal_skill = 1`)
        2. Each skill name is converted to a vector embedding using sentence-transformers
        3. Model can be fine-tuned on labeled role-skill pairs to learn associations
        4. When a role is queried, it's normalized and embedded
        5. Cosine similarity finds the most relevant skills
        6. Results above threshold (0.45) are returned

        ## Training

        Upload CSV training data with role-skill mappings, then train the model.
        The trained model learns associations like "MERN Stack Developer" → MongoDB, React, etc.

        ### Training Data Format

        ```csv
        role,skills
        "MERN Stack Developer","MongoDB,Express.js,React.js,Node.js"
        "Data Scientist","Python,Machine Learning,Pandas,TensorFlow"
        ```

        ## Search Methods

        | Method | Description |
        |--------|-------------|
        | `mapped` | Skills from training data (direct lookup) |
        | `hybrid` | Combination of mapped + semantic |
        | `semantic` | Pure vector similarity (fallback) |
            """,
    version="2.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Skill Suggestion API",
    },
    license_info={
        "name": "MIT",
    },
)

# Include API routers
app.include_router(suggest_router, tags=["Suggestions"])
app.include_router(refresh_router, tags=["Management"])
app.include_router(train_router, tags=["Training"])
app.include_router(kb_router, tags=["Knowledge Base"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Skill Suggestion Service",
        "version": "2.0.0",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json"
        },
        "endpoints": {
            "suggestions": {
                "suggest_skills": "POST /suggest-skills"
            },
            "management": {
                "refresh_vectors": "POST /skills/refresh-vectors",
                "health": "GET /skills/health"
            },
            "training": {
                "train_model": "POST /model/train",
                "model_status": "GET /model/status",
                "upload_training_data": "POST /model/upload-training-data",
                "list_training_files": "GET /model/training-files",
                "delete_model": "DELETE /model/trained"
            },
            "knowledge_base": {
                "get_mappings": "GET /knowledge-base/mappings",
                "add_mapping": "POST /knowledge-base/mappings",
                "update_mapping": "PUT /knowledge-base/mappings",
                "delete_mapping": "DELETE /knowledge-base/mappings/{role}"
            }
        }
    }
