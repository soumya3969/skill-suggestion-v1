"""
Text normalization module for role and skill processing.
Handles cleaning, noise word removal, and standardization.
"""

import re
from typing import Set

# Noise words to remove from role text
# These are common role qualifiers that don't add semantic value for skill matching
NOISE_WORDS: Set[str] = {
    "senior",
    "junior",
    "lead",
    "engineer",
    "developer",
    "software",
    "staff",
    "principal",
    "associate",
    "intern",
    "trainee",
    "specialist",
    "consultant",
    "analyst",
    "architect",
    "manager",
    "head",
    "chief",
    "vp",
    "director",
}


def normalize_text(text: str) -> str:
    """
    Normalize text by converting to lowercase and removing extra whitespace.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
    
    # Convert to lowercase
    normalized = text.lower().strip()
    
    # Remove special characters except alphanumeric and spaces
    normalized = re.sub(r"[^a-z0-9\s\-\+\#\.]", " ", normalized)
    
    # Collapse multiple spaces into single space
    normalized = re.sub(r"\s+", " ", normalized)
    
    return normalized.strip()


def remove_noise_words(text: str) -> str:
    """
    Remove noise words from text that don't contribute to skill matching.
    
    Args:
        text: Input text (should be pre-normalized)
        
    Returns:
        Text with noise words removed
    """
    if not text:
        return ""
    
    words = text.split()
    filtered_words = [word for word in words if word not in NOISE_WORDS]
    
    # If all words were noise words, return original to avoid empty string
    if not filtered_words:
        return text
    
    return " ".join(filtered_words)


def normalize_role(role: str) -> str:
    """
    Full normalization pipeline for role text.
    
    Steps:
    1. Basic text normalization (lowercase, remove special chars)
    2. Remove noise words
    3. Final cleanup
    
    Args:
        role: Raw role/designation string
        
    Returns:
        Normalized role string ready for embedding
        
    Example:
        >>> normalize_role("Senior MERN Stack Developer")
        'mern stack'
    """
    if not role:
        return ""
    
    # Step 1: Basic normalization
    normalized = normalize_text(role)
    
    # Step 2: Remove noise words
    cleaned = remove_noise_words(normalized)
    
    # Step 3: Final cleanup
    result = re.sub(r"\s+", " ", cleaned).strip()
    
    return result


def normalize_skill_name(skill_name: str) -> str:
    """
    Normalize skill name for embedding.
    Less aggressive than role normalization - preserves more information.
    
    Args:
        skill_name: Raw skill name from database
        
    Returns:
        Normalized skill name
    """
    if not skill_name:
        return ""
    
    return normalize_text(skill_name)
