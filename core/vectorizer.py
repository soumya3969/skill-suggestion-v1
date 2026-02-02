"""
Vectorization module for skill embeddings.
Handles model loading, embedding generation, and vector persistence.
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from core.normalizer import normalize_skill_name

logger = logging.getLogger(__name__)

# Model configuration
BASE_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384  # Dimension for all-MiniLM-L6-v2

# File paths for vector storage
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
TRAINED_MODEL_PATH = MODELS_DIR / "skill-matcher-v1"
VECTORS_FILE = DATA_DIR / "skill_vectors.npy"
IDS_FILE = DATA_DIR / "skill_ids.npy"


def get_model_to_use() -> str:
    """
    Determine which model to use.
    Returns trained model path if available, otherwise base model name.
    """
    if TRAINED_MODEL_PATH.exists():
        logger.info(f"Using trained model: {TRAINED_MODEL_PATH}")
        return str(TRAINED_MODEL_PATH)
    logger.info(f"Using base model: {BASE_MODEL_NAME}")
    return BASE_MODEL_NAME


class SkillVectorizer:
    """
    Handles skill vectorization using sentence-transformers.
    Manages model loading, embedding generation, and persistence.
    """
    
    def __init__(self):
        """Initialize vectorizer with the sentence-transformer model."""
        self._model: Optional[SentenceTransformer] = None
        self._model_path: Optional[str] = None
    
    def _load_model(self) -> SentenceTransformer:
        """Load the appropriate model (trained or base)."""
        model_path = get_model_to_use()
        logger.info(f"Loading embedding model: {model_path}")
        model = SentenceTransformer(model_path)
        self._model_path = model_path
        logger.info("Embedding model loaded successfully")
        return model
    
    @property
    def model(self) -> SentenceTransformer:
        """
        Lazy load the embedding model.
        Model is loaded only when first needed.
        Checks if trained model has changed and reloads if necessary.
        """
        current_model_path = get_model_to_use()
        
        # Reload if model path changed (e.g., trained model added/removed)
        if self._model is None or self._model_path != current_model_path:
            self._model = self._load_model()
        
        return self._model
    
    def reload_model(self) -> None:
        """Force reload the model (used after training)."""
        self._model = None
        self._model_path = None
        _ = self.model  # Trigger reload
    
    def unload_model(self) -> None:
        """
        Unload the model from memory to release file handles.
        Used before retraining to avoid Windows file locking issues.
        """
        if self._model is not None:
            del self._model
            self._model = None
            self._model_path = None
            # Force garbage collection to release file handles
            import gc
            gc.collect()
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate normalized embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            Numpy array of shape (n_texts, embedding_dim) with L2-normalized vectors
        """
        if not texts:
            return np.array([]).reshape(0, EMBEDDING_DIMENSION)
        
        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True  # L2 normalization for cosine similarity
        )
        
        return embeddings.astype(np.float32)
    
    def generate_single_embedding(self, text: str) -> np.ndarray:
        """
        Generate normalized embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            Numpy array of shape (embedding_dim,) with L2-normalized vector
        """
        if not text:
            raise ValueError("Cannot generate embedding for empty text")
        
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        return embedding.astype(np.float32)


def build_skill_vectors(skills: List[Tuple[int, str]]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build normalized vectors for all skills.
    
    Args:
        skills: List of (skill_id, skill_name) tuples
        
    Returns:
        Tuple of (vectors array, ids array)
        - vectors: shape (n_skills, embedding_dim), L2-normalized
        - ids: shape (n_skills,), integer skill IDs
    """
    if not skills:
        logger.warning("No skills provided for vectorization")
        return (
            np.array([]).reshape(0, EMBEDDING_DIMENSION).astype(np.float32),
            np.array([]).astype(np.int32)
        )
    
    logger.info(f"Building vectors for {len(skills)} skills")
    
    # Extract and normalize skill names
    skill_ids = [s[0] for s in skills]
    skill_names = [normalize_skill_name(s[1]) for s in skills]
    
    # Generate embeddings
    vectorizer = SkillVectorizer()
    vectors = vectorizer.generate_embeddings(skill_names)
    
    logger.info(f"Generated {len(vectors)} skill vectors")
    
    return vectors, np.array(skill_ids, dtype=np.int32)


def save_vectors(vectors: np.ndarray, skill_ids: np.ndarray) -> None:
    """
    Persist vectors and IDs to disk.
    
    Args:
        vectors: Skill embedding vectors
        skill_ids: Corresponding skill IDs
    """
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use temp files without .npy suffix (np.save adds it automatically)
    temp_vectors_base = DATA_DIR / "skill_vectors_tmp"
    temp_ids_base = DATA_DIR / "skill_ids_tmp"
    temp_vectors_file = DATA_DIR / "skill_vectors_tmp.npy"
    temp_ids_file = DATA_DIR / "skill_ids_tmp.npy"
    
    try:
        # np.save automatically adds .npy extension
        np.save(temp_vectors_base, vectors)
        np.save(temp_ids_base, skill_ids)
        
        # Remove existing target files first (required on Windows)
        if VECTORS_FILE.exists():
            VECTORS_FILE.unlink()
        if IDS_FILE.exists():
            IDS_FILE.unlink()
        
        # Rename temp files to final names
        temp_vectors_file.rename(VECTORS_FILE)
        temp_ids_file.rename(IDS_FILE)
        
        logger.info(f"Saved vectors to {VECTORS_FILE}")
        logger.info(f"Saved IDs to {IDS_FILE}")
        
    except Exception as e:
        # Cleanup temp files on failure
        temp_vectors_file.unlink(missing_ok=True)
        temp_ids_file.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to save vectors: {e}")


def load_vectors() -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Load vectors and IDs from disk.
    
    Returns:
        Tuple of (vectors, skill_ids) or (None, None) if files don't exist
    """
    if not VECTORS_FILE.exists() or not IDS_FILE.exists():
        logger.warning("Vector files not found on disk")
        return None, None
    
    try:
        vectors = np.load(VECTORS_FILE)
        skill_ids = np.load(IDS_FILE)
        
        logger.info(f"Loaded {len(vectors)} vectors from disk")
        
        return vectors, skill_ids
        
    except Exception as e:
        logger.error(f"Failed to load vectors: {e}")
        return None, None


def vectors_exist() -> bool:
    """Check if vector files exist on disk."""
    return VECTORS_FILE.exists() and IDS_FILE.exists()
