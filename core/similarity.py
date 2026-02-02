"""
Similarity computation module.
Handles cosine similarity search over skill vectors.
Supports hybrid search: direct role mapping + semantic fallback.
"""

import threading
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple, Dict

import numpy as np

from core.vectorizer import (
    SkillVectorizer,
    build_skill_vectors,
    save_vectors,
    load_vectors,
    vectors_exist,
)
from core.db import fetch_active_skills
from core.normalizer import normalize_role, normalize_text

logger = logging.getLogger(__name__)

# Similarity threshold for filtering results
SIMILARITY_THRESHOLD = 0.45

# Confidence score for mapped skills (from training data)
MAPPED_SKILL_CONFIDENCE = 0.95


@dataclass
class SkillMatch:
    """Represents a matched skill with confidence score."""
    skill_id: int
    skill_name: str
    confidence: float
    source: str = "semantic"  # "mapped" or "semantic"


class SkillSearchEngine:
    """
    In-memory skill search engine using cosine similarity.
    Supports hybrid search: direct role mapping + semantic fallback.
    Thread-safe with read-write locking for concurrent access.
    """
    
    def __init__(self):
        """Initialize the search engine with empty state."""
        self._vectors: Optional[np.ndarray] = None
        self._skill_ids: Optional[np.ndarray] = None
        self._skill_names: Dict[int, str] = {}  # skill_id -> skill_name mapping
        self._skill_name_to_id: Dict[str, int] = {}  # normalized_skill_name -> skill_id
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
        """Load skill names from database for result formatting and reverse lookup."""
        try:
            skills = fetch_active_skills()
            self._skill_names = {skill_id: name for skill_id, name in skills}
            # Build reverse lookup: normalized name -> skill_id
            self._skill_name_to_id = {}
            for skill_id, name in skills:
                normalized = normalize_text(name).lower()
                self._skill_name_to_id[normalized] = skill_id
        except Exception as e:
            logger.error(f"Failed to load skill names: {e}")
            self._skill_names = {}
            self._skill_name_to_id = {}
    
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
    
    def refresh_vectors(self, reload_model: bool = True) -> int:
        """
        Refresh vectors from database.
        Thread-safe: uses lock to ensure atomic update.
        
        Args:
            reload_model: If True, reload the embedding model (use after training)
        
        Returns:
            Number of skills indexed after refresh
        """
        logger.info("Starting vector refresh")
        
        # Reload model if requested (e.g., after training new model)
        if reload_model and self._vectorizer is not None:
            logger.info("Reloading embedding model")
            self._vectorizer.reload_model()
        
        # Build new vectors outside the lock
        skills = fetch_active_skills()
        
        if not skills:
            logger.warning("No active skills found during refresh")
            with self._lock:
                self._vectors = np.array([]).reshape(0, 384).astype(np.float32)
                self._skill_ids = np.array([]).astype(np.int32)
                self._skill_names = {}
            return 0
        
        # Build vectors using fresh vectorizer
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
    
    def find_skill_by_name(
        self,
        skill_name: str,
        fuzzy_threshold: float = 0.75
    ) -> Optional[Tuple[int, str, float]]:
        """
        Find a skill in the database by name.
        Uses exact match first, then fuzzy matching.
        
        Args:
            skill_name: The skill name to search for
            fuzzy_threshold: Minimum similarity for fuzzy match
            
        Returns:
            Tuple of (skill_id, actual_name, match_score) or None
        """
        normalized = normalize_text(skill_name).lower()
        
        # Exact match
        if normalized in self._skill_name_to_id:
            skill_id = self._skill_name_to_id[normalized]
            return skill_id, self._skill_names[skill_id], 1.0
        
        # Fuzzy match
        best_match = None
        best_score = 0.0
        best_id = None
        
        for db_name, skill_id in self._skill_name_to_id.items():
            score = SequenceMatcher(None, normalized, db_name).ratio()
            
            # Boost score if one contains the other
            if normalized in db_name or db_name in normalized:
                score = max(score, 0.85)
            
            if score > best_score:
                best_score = score
                best_match = db_name
                best_id = skill_id
        
        if best_id and best_score >= fuzzy_threshold:
            return best_id, self._skill_names[best_id], best_score
        
        return None
    
    def search_by_mapped_skills(
        self,
        skill_names: List[str],
        limit: int = 10
    ) -> List[SkillMatch]:
        """
        Search for skills by their names (from role mapping).
        
        Args:
            skill_names: List of skill names to find
            limit: Maximum results to return
            
        Returns:
            List of SkillMatch objects for found skills
        """
        results = []
        seen_ids = set()
        
        for skill_name in skill_names:
            if len(results) >= limit:
                break
            
            match = self.find_skill_by_name(skill_name)
            if match and match[0] not in seen_ids:
                skill_id, actual_name, match_score = match
                # Confidence based on how well the name matched
                confidence = round(MAPPED_SKILL_CONFIDENCE * match_score, 2)
                results.append(SkillMatch(
                    skill_id=skill_id,
                    skill_name=actual_name,
                    confidence=confidence,
                    source="mapped"
                ))
                seen_ids.add(skill_id)
        
        return results
    
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
    
    def hybrid_search(
        self,
        role: str,
        limit: int = 10,
        threshold: float = SIMILARITY_THRESHOLD,
        use_role_mapping: bool = True
    ) -> Tuple[str, List[SkillMatch], str]:
        """
        Hybrid search: uses role mapping if available, falls back to semantic search.
        
        Args:
            role: Job role or designation
            limit: Maximum results to return
            threshold: Minimum similarity for semantic search
            use_role_mapping: Whether to use role-skill mappings
            
        Returns:
            Tuple of (normalized_role, list of SkillMatch, search_method)
            search_method is "mapped", "hybrid", or "semantic"
        """
        if not self._initialized:
            raise RuntimeError("Search engine not initialized.")
        
        if not role or not role.strip():
            raise ValueError("Role cannot be empty")
        
        # Import here to avoid circular imports
        from core.role_mapper import get_role_mapper
        
        normalized_role = normalize_role(role)
        if not normalized_role:
            normalized_role = normalize_text(role).lower()
        
        mapper = get_role_mapper()
        mapped_results = []
        search_method = "semantic"
        
        # Try role mapping first
        if use_role_mapping and mapper.is_loaded:
            matched_role, skill_names = mapper.get_skills_for_role(role)
            
            if skill_names:
                logger.info(f"Found role mapping for '{role}' -> {len(skill_names)} skills")
                mapped_results = self.search_by_mapped_skills(skill_names, limit)
                
                if mapped_results:
                    search_method = "mapped"
                    
                    # If we have enough mapped results, return them
                    if len(mapped_results) >= limit:
                        return normalized_role, mapped_results[:limit], search_method
        
        # Semantic search (either as fallback or to supplement)
        _, semantic_results = self.search(role, limit=limit, threshold=threshold)
        
        if not mapped_results:
            # Pure semantic search
            return normalized_role, semantic_results, "semantic"
        
        # Hybrid: combine mapped + semantic, avoiding duplicates
        search_method = "hybrid"
        combined = mapped_results.copy()
        seen_ids = {m.skill_id for m in combined}
        
        for result in semantic_results:
            if result.skill_id not in seen_ids and len(combined) < limit:
                # Lower confidence for semantic results in hybrid mode
                result.source = "semantic"
                combined.append(result)
                seen_ids.add(result.skill_id)
        
        return normalized_role, combined[:limit], search_method


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
