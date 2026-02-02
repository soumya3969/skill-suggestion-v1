"""
Training module for fine-tuning skill suggestion model.
Uses contrastive learning to learn role-skill associations.
"""

import csv
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
TRAINING_DATA_DIR = BASE_DIR / "training_data"
MODELS_DIR = BASE_DIR / "models"
DEFAULT_TRAINING_FILE = TRAINING_DATA_DIR / "role_skills.csv"
TRAINED_MODEL_PATH = MODELS_DIR / "skill-matcher-v1"

# Training configuration
DEFAULT_BASE_MODEL = "all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 16
DEFAULT_EPOCHS = 10


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    base_model: str = DEFAULT_BASE_MODEL
    batch_size: int = DEFAULT_BATCH_SIZE
    epochs: int = DEFAULT_EPOCHS
    warmup_steps: int = 100
    output_path: Optional[Path] = None
    
    def __post_init__(self):
        if self.output_path is None:
            self.output_path = TRAINED_MODEL_PATH


@dataclass
class TrainingResult:
    """Result of a training run."""
    success: bool
    model_path: str
    training_pairs: int
    epochs: int
    message: str


def load_training_data_from_csv(csv_path: Path) -> List[Tuple[str, List[str]]]:
    """
    Load training data from CSV file.
    
    Expected CSV format:
        role,skills
        "MERN Stack Developer","MongoDB,Express.js,React.js,Node.js"
        
    Args:
        csv_path: Path to CSV file
        
    Returns:
        List of (role, [skills]) tuples
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Training data file not found: {csv_path}")
    
    training_data = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Validate headers
        if 'role' not in reader.fieldnames or 'skills' not in reader.fieldnames:
            raise ValueError("CSV must have 'role' and 'skills' columns")
        
        for row in reader:
            role = row['role'].strip()
            skills_str = row['skills'].strip()
            
            if not role or not skills_str:
                continue
            
            # Parse comma-separated skills
            skills = [s.strip() for s in skills_str.split(',') if s.strip()]
            
            if skills:
                training_data.append((role, skills))
    
    logger.info(f"Loaded {len(training_data)} role-skill mappings from {csv_path}")
    return training_data


def create_training_examples(training_data: List[Tuple[str, List[str]]]) -> List[InputExample]:
    """
    Create training examples from role-skill pairs.
    
    Each (role, skill) pair becomes one training example.
    MultipleNegativesRankingLoss will use other skills in the batch as negatives.
    
    Args:
        training_data: List of (role, [skills]) tuples
        
    Returns:
        List of InputExample objects for training
    """
    examples = []
    
    for role, skills in training_data:
        for skill in skills:
            # Create positive pair: role and its associated skill
            examples.append(InputExample(texts=[role, skill]))
    
    logger.info(f"Created {len(examples)} training examples")
    return examples


def train_model(
    training_file: Optional[Path] = None,
    config: Optional[TrainingConfig] = None
) -> TrainingResult:
    """
    Train the skill suggestion model on role-skill pairs.
    
    Uses MultipleNegativesRankingLoss which:
    - Treats (role, skill) as positive pairs
    - Uses other skills in the batch as in-batch negatives
    - Learns to place roles close to their associated skills in embedding space
    
    Args:
        training_file: Path to CSV training data (default: training_data/role_skills.csv)
        config: Training configuration (default: uses defaults)
        
    Returns:
        TrainingResult with success status and details
    """
    if config is None:
        config = TrainingConfig()
    
    if training_file is None:
        training_file = DEFAULT_TRAINING_FILE
    
    try:
        # Load training data
        logger.info(f"Loading training data from {training_file}")
        training_data = load_training_data_from_csv(training_file)
        
        if not training_data:
            return TrainingResult(
                success=False,
                model_path="",
                training_pairs=0,
                epochs=0,
                message="No training data found in CSV"
            )
        
        # Create training examples
        train_examples = create_training_examples(training_data)
        
        if len(train_examples) < config.batch_size:
            logger.warning(
                f"Training examples ({len(train_examples)}) less than batch size "
                f"({config.batch_size}). Reducing batch size."
            )
            config.batch_size = max(2, len(train_examples) // 2)
        
        # Load base model
        logger.info(f"Loading base model: {config.base_model}")
        model = SentenceTransformer(config.base_model)
        
        # Create data loader
        train_dataloader = DataLoader(
            train_examples,
            shuffle=True,
            batch_size=config.batch_size
        )
        
        # Define loss function
        # MultipleNegativesRankingLoss: for each (anchor, positive) pair,
        # other positives in the batch serve as negatives
        train_loss = losses.MultipleNegativesRankingLoss(model)
        
        # Ensure output directory exists
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Train the model
        logger.info(f"Starting training for {config.epochs} epochs")
        model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            epochs=config.epochs,
            warmup_steps=config.warmup_steps,
            show_progress_bar=True,
            output_path=str(config.output_path)
        )
        
        logger.info(f"Model saved to {config.output_path}")
        
        return TrainingResult(
            success=True,
            model_path=str(config.output_path),
            training_pairs=len(train_examples),
            epochs=config.epochs,
            message=f"Successfully trained model on {len(train_examples)} pairs"
        )
        
    except FileNotFoundError as e:
        logger.error(f"Training file not found: {e}")
        return TrainingResult(
            success=False,
            model_path="",
            training_pairs=0,
            epochs=0,
            message=str(e)
        )
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return TrainingResult(
            success=False,
            model_path="",
            training_pairs=0,
            epochs=0,
            message=f"Training failed: {str(e)}"
        )


def trained_model_exists() -> bool:
    """Check if a trained model exists."""
    return TRAINED_MODEL_PATH.exists()


def get_model_path() -> Path:
    """
    Get the path to the model to use.
    Returns trained model path if exists, otherwise base model name.
    """
    if trained_model_exists():
        return TRAINED_MODEL_PATH
    return None


def delete_trained_model() -> bool:
    """
    Delete the trained model to revert to base model.
    
    Returns:
        True if model was deleted, False if it didn't exist
    """
    import shutil
    
    if not trained_model_exists():
        return False
    
    try:
        shutil.rmtree(TRAINED_MODEL_PATH)
        logger.info(f"Deleted trained model at {TRAINED_MODEL_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        raise RuntimeError(f"Failed to delete model: {e}")
