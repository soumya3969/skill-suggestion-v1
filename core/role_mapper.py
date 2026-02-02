"""
Role-to-Skill mapping module.
Provides direct mappings from training data for known roles.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from difflib import SequenceMatcher

from core.normalizer import normalize_role, normalize_text

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
TRAINING_DATA_DIR = BASE_DIR / "training_data"
DEFAULT_TRAINING_FILE = TRAINING_DATA_DIR / "role_skills.csv"


class RoleSkillMapper:
    """
    Maps roles to skills using training data.
    Provides exact and fuzzy matching for known roles.
    """
    
    def __init__(self):
        """Initialize empty mapper."""
        # normalized_role -> list of skill names
        self._role_to_skills: Dict[str, List[str]] = {}
        # All normalized roles for fuzzy matching
        self._known_roles: Set[str] = set()
        self._loaded = False
    
    def load_from_csv(self, csv_path: Optional[Path] = None) -> int:
        """
        Load role-skill mappings from CSV file.
        
        Args:
            csv_path: Path to CSV file (default: training_data/role_skills.csv)
            
        Returns:
            Number of roles loaded
        """
        if csv_path is None:
            csv_path = DEFAULT_TRAINING_FILE
        
        if not csv_path.exists():
            logger.warning(f"Training data file not found: {csv_path}")
            return 0
        
        self._role_to_skills.clear()
        self._known_roles.clear()
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    role = row.get('role', '').strip()
                    skills_str = row.get('skills', '').strip()
                    
                    if not role or not skills_str:
                        continue
                    
                    # Normalize the role
                    normalized = normalize_role(role)
                    if not normalized:
                        normalized = normalize_text(role)
                    
                    # Parse skills
                    skills = [s.strip() for s in skills_str.split(',') if s.strip()]
                    
                    if skills:
                        self._role_to_skills[normalized] = skills
                        self._known_roles.add(normalized)
            
            self._loaded = True
            logger.info(f"Loaded {len(self._role_to_skills)} role mappings from {csv_path}")
            return len(self._role_to_skills)
            
        except Exception as e:
            logger.error(f"Failed to load role mappings: {e}")
            return 0
    
    def get_skills_for_role(
        self,
        role: str,
        fuzzy_threshold: float = 0.7
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        """
        Get skills for a role using exact or fuzzy matching.
        
        Args:
            role: The role to look up
            fuzzy_threshold: Minimum similarity for fuzzy match (0-1)
            
        Returns:
            Tuple of (matched_role, list of skills) or (None, None) if no match
        """
        if not self._loaded or not self._role_to_skills:
            return None, None
        
        # Normalize input role
        normalized = normalize_role(role)
        if not normalized:
            normalized = normalize_text(role)
        
        # Try exact match first
        if normalized in self._role_to_skills:
            logger.info(f"Exact role match: '{normalized}'")
            return normalized, self._role_to_skills[normalized]
        
        # Try fuzzy matching
        best_match = None
        best_score = 0.0
        
        for known_role in self._known_roles:
            # Calculate similarity
            score = SequenceMatcher(None, normalized, known_role).ratio()
            
            # Also check if one contains the other
            if normalized in known_role or known_role in normalized:
                score = max(score, 0.85)
            
            if score > best_score:
                best_score = score
                best_match = known_role
        
        if best_match and best_score >= fuzzy_threshold:
            logger.info(f"Fuzzy role match: '{normalized}' -> '{best_match}' (score: {best_score:.2f})")
            return best_match, self._role_to_skills[best_match]
        
        logger.debug(f"No role match for: '{normalized}' (best: '{best_match}', score: {best_score:.2f})")
        return None, None
    
    def get_all_mappings(self) -> Dict[str, List[str]]:
        """Get all role-skill mappings."""
        return self._role_to_skills.copy()
    
    @property
    def is_loaded(self) -> bool:
        """Check if mappings are loaded."""
        return self._loaded
    
    @property
    def role_count(self) -> int:
        """Get number of mapped roles."""
        return len(self._role_to_skills)


# Global mapper instance
_role_mapper: Optional[RoleSkillMapper] = None


def get_role_mapper() -> RoleSkillMapper:
    """Get the global role mapper instance."""
    global _role_mapper
    if _role_mapper is None:
        _role_mapper = RoleSkillMapper()
    return _role_mapper


def initialize_role_mapper(csv_path: Optional[Path] = None) -> int:
    """
    Initialize the global role mapper from CSV.
    
    Returns:
        Number of roles loaded
    """
    mapper = get_role_mapper()
    return mapper.load_from_csv(csv_path)


def reload_role_mapper(csv_path: Optional[Path] = None) -> int:
    """
    Reload the role mapper from CSV.
    
    Returns:
        Number of roles loaded
    """
    return initialize_role_mapper(csv_path)
