"""
Similarity computation module.
Handles cosine similarity search over skill vectors.
"""

import threading
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from core.vectorizer import (
    SkillVectorizer,
    build_skill_vectors,
    save_vectors,
    load_vectors,
    vectors_exist,
)
from core.db import fetch_active_skills
from core.normalizer import normalize_role

logger = logging.getLogger(__name__)

# Similarity threshold for filtering results
SIMILARITY_THRESHOLD = 0.45


@dataclass
class SkillMatch:
    """Represents a matched skill with confidence score."""
    skill_id: int
    skill_name: str
    confidence: float


class SkillSearchEngine:
    """
    In-memory skill search engine using cosine similarity.
    Thread-safe with read-write locking for concurrent access.
    """
    
    def __init__(self):
        """Initialize the search engine with empty state."""
        self._vectors: Optional[np.ndarray] = None
        self._skill_ids: Optional[np.ndarray] = None
        self._skill_names: dict = {}  # skill_id -> skill_name mapping
        self._vectorizer: Optional[SkillVectorizer] = None
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._initialized = False
    
    @property
    def vectorizer(self) -> SkillVectorizer:
        """Lazy-load vectorizer instance."""
        if self._vectorizer is None:
            self._vectorizer = SkillVectorizer()
        return self._vectorizer
    
    @property
    def is_initialized(self) -> bool:
        """Check if engine has loaded vectors."""
        return self._initialized
    
    @property
    def skill_count(self) -> int:
        """Return number of indexed skills."""
        with self._lock:
            if self._skill_ids is None:
                return 0
            return len(self._skill_ids)
    
    def initialize(self) -> None:
        """
        Initialize the search engine.
        Loads existing vectors from disk, or builds new ones from database.
        """
        logger.info("Initializing skill search engine")
        
        with self._lock:
            # Try loading from disk first
            if vectors_exist():
                logger.info("Loading existing vectors from disk")
                vectors, skill_ids = load_vectors()
                
                if vectors is not None and skill_ids is not None:
                    self._vectors = vectors
                    self._skill_ids = skill_ids
                    
                    # Load skill names from database
                    self._load_skill_names()
                    self._initialized = True
                    logger.info(f"Initialized with {len(skill_ids)} skills from disk")
                    return
            
            # Build vectors from database
            logger.info("Building vectors from database")
            self._build_and_load_vectors()
    
    def _load_skill_names(self) -> None:
        """Load skill names from database for result formatting."""
        try:
            skills = fetch_active_skills()
            self._skill_names = {skill_id: name for skill_id, name in skills}
        except Exception as e:
            logger.error(f"Failed to load skill names: {e}")
            self._skill_names = {}
    
    def _build_and_load_vectors(self) -> None:
        """
        Fetch skills from database, build vectors, and load into memory.
        Also persists vectors to disk.
        """
        # Fetch active skills
        skills = fetch_active_skills()
        
        if not skills:
            logger.warning("No active skills found in database")
            self._vectors = np.array([]).reshape(0, 384).astype(np.float32)
            self._skill_ids = np.array([]).astype(np.int32)
            self._skill_names = {}
            self._initialized = True
            return
        
        # Build skill name mapping
        self._skill_names = {skill_id: name for skill_id, name in skills}
        
        # Build vectors
        vectors, skill_ids = build_skill_vectors(skills)
        
        # Save to disk
        save_vectors(vectors, skill_ids)
        
        # Load into memory
        self._vectors = vectors
        self._skill_ids = skill_ids
        self._initialized = True
        
        logger.info(f"Built and loaded {len(skill_ids)} skill vectors")
    
    def refresh_vectors(self) -> int:
        """
        Refresh vectors from database.
        Thread-safe: uses lock to ensure atomic update.
        
        Returns:
            Number of skills indexed after refresh
        """
        logger.info("Starting vector refresh")
        
        # Build new vectors outside the lock
        skills = fetch_active_skills()
        
        if not skills:
            logger.warning("No active skills found during refresh")
            with self._lock:
                self._vectors = np.array([]).reshape(0, 384).astype(np.float32)
                self._skill_ids = np.array([]).astype(np.int32)
                self._skill_names = {}
            return 0
        
        # Build vectors
        new_names = {skill_id: name for skill_id, name in skills}
        new_vectors, new_ids = build_skill_vectors(skills)
        
        # Save to disk
        save_vectors(new_vectors, new_ids)
        
        # Atomic swap with lock
        with self._lock:
            self._vectors = new_vectors
            self._skill_ids = new_ids
            self._skill_names = new_names
        
        logger.info(f"Refresh complete: {len(new_ids)} skills indexed")
        return len(new_ids)
    
    def search(
        self,
        role: str,
        limit: int = 10,
        threshold: float = SIMILARITY_THRESHOLD
    ) -> Tuple[str, List[SkillMatch]]:
        """
        Search for skills matching a role description.
        
        Args:
            role: Job role or designation to match against
            limit: Maximum number of results to return
            threshold: Minimum similarity score (0-1)
            
        Returns:
            Tuple of (normalized_role, list of SkillMatch objects)
            
        Raises:
            RuntimeError: If engine not initialized
            ValueError: If role is empty
        """
        if not self._initialized:
            raise RuntimeError("Search engine not initialized. Call initialize() first.")
        
        if not role or not role.strip():
            raise ValueError("Role cannot be empty")
        
        # Normalize the role
        normalized_role = normalize_role(role)
        
        if not normalized_role:
            logger.warning(f"Role '{role}' normalized to empty string")
            return role.lower().strip(), []
        
        with self._lock:
            if self._vectors is None or len(self._vectors) == 0:
                logger.warning("No skill vectors available")
                return normalized_role, []
            
            # Generate embedding for the query
            query_vector = self.vectorizer.generate_single_embedding(normalized_role)
            
            # Compute cosine similarity
            # Since both vectors are L2-normalized, dot product = cosine similarity
            similarities = np.dot(self._vectors, query_vector)
            
            # Get indices sorted by similarity (descending)
            sorted_indices = np.argsort(similarities)[::-1]
            
            # Filter and collect results
            results = []
            for idx in sorted_indices:
                score = float(similarities[idx])
                
                # Apply threshold
                if score < threshold:
                    break
                
                skill_id = int(self._skill_ids[idx])
                skill_name = self._skill_names.get(skill_id, "Unknown")
                
                results.append(SkillMatch(
                    skill_id=skill_id,
                    skill_name=skill_name,
                    confidence=round(score, 2)
                ))
                
                if len(results) >= limit:
                    break
            
            return normalized_role, results


# Global search engine instance
_search_engine: Optional[SkillSearchEngine] = None


def get_search_engine() -> SkillSearchEngine:
    """
    Get the global search engine instance.
    Creates one if not already initialized.
    """
    global _search_engine
    if _search_engine is None:
        _search_engine = SkillSearchEngine()
    return _search_engine


def initialize_search_engine() -> None:
    """Initialize the global search engine."""
    engine = get_search_engine()
    engine.initialize()


def refresh_search_engine() -> int:
    """
    Refresh vectors in the global search engine.
    
    Returns:
        Number of skills indexed after refresh
    """
    engine = get_search_engine()
    return engine.refresh_vectors()
