# Skill Suggestion Service

A semantic skill suggestion service that uses vector similarity to recommend relevant skills based on job roles. Supports custom model training on labeled role-skill pairs.

## Features

- **Semantic Search**: Uses sentence-transformers to understand skill context
- **Trainable Model**: Fine-tune on role-skill pairs for learned associations
- **Vector-based Matching**: Cosine similarity for accurate skill matching
- **Read-only Database Access**: No modifications to production data
- **Hot Reload**: Refresh vectors via API without service restart
- **Thread-safe**: Concurrent request handling with proper locking

## Tech Stack

- Python 3.9+
- FastAPI
- sentence-transformers
- NumPy / PyTorch
- psycopg2
- PostgreSQL (read-only)

## Project Structure

```
skill_suggest_v1/
├── data/
│   ├── skill_vectors.npy    # Skill embeddings
│   └── skill_ids.npy        # Skill ID mapping
├── models/
│   └── skill-matcher-v1/    # Trained model (after training)
├── training_data/
│   └── role_skills.csv      # Training data
├── core/
│   ├── db.py                # Database operations
│   ├── vectorizer.py        # Embedding generation
│   ├── similarity.py        # Search engine
│   ├── normalizer.py        # Text normalization
│   └── trainer.py           # Model training
├── api/
│   ├── suggest.py           # Suggestion endpoint
│   ├── refresh.py           # Refresh endpoint
│   └── train.py             # Training endpoints
├── app.py                   # FastAPI application
├── requirements.txt
└── README.md
```
### Dev setup
```bash
# Create a new venv with Python 3.11/3.12
py -3.11 -m venv venv
# or
py -3.12 -m venv venv
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file or set environment variables:

```bash
DB_NAME=skill_matching
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5433
```

### 3. Run the Service

```bash
uvicorn app:app --reload
```

The service will:
1. Connect to PostgreSQL
2. Load or build skill vectors
3. Start accepting requests on http://localhost:8000

## API Endpoints

### POST /suggest-skills

Suggest skills for a job role.

**Request:**
```json
{
  "role": "Senior MERN Stack Developer",
  "limit": 10
}
```

**Response:**
```json
{
  "normalized_role": "mern stack",
  "skills": [
    {
      "skill_id": 15241,
      "skill_name": "React js",
      "confidence": 0.91
    },
    {
      "skill_id": 15242,
      "skill_name": "Node.js",
      "confidence": 0.87
    }
  ]
}
```

### POST /skills/refresh-vectors

Refresh skill vectors from database.

**Response:**
```json
{
  "status": "success",
  "skills_indexed": 5432,
  "duration_seconds": 12.34,
  "message": "Successfully refreshed 5432 skill vectors"
}
```

### GET /skills/health

Check service health.

**Response:**
```json
{
  "status": "healthy",
  "skills_loaded": 5432,
  "initialized": true
}
```

### POST /model/train

Train the model on role-skill pairs.

**Request:**
```json
{
  "training_file": "role_skills.csv",
  "epochs": 10,
  "batch_size": 16
}
```

**Response:**
```json
{
  "success": true,
  "model_path": "models/skill-matcher-v1",
  "training_pairs": 245,
  "epochs": 10,
  "message": "Successfully trained model on 245 pairs"
}
```

### GET /model/status

Check if trained model exists.

**Response:**
```json
{
  "trained_model_exists": true,
  "model_path": "models/skill-matcher-v1",
  "skills_indexed": 5432,
  "using_trained_model": true
}
```

### DELETE /model/trained

Delete trained model and revert to base model.

## How It Works

### 1. Skill Vectorization (Startup)

- Fetches active skills from database (`curatal_skill = 1`)
- Generates 384-dimensional embeddings using sentence-transformers
- Uses trained model if available, otherwise base model (all-MiniLM-L6-v2)
- L2-normalizes all vectors for efficient cosine similarity
- Saves vectors to disk (`.npy` files)
- Loads vectors into memory

### 2. Skill Suggestion (Query)

- Normalizes input role (lowercase, remove noise words)
- Generates embedding for normalized role
- Computes cosine similarity against all skill vectors
- Returns top-N skills above threshold (0.45)

### 3. Vector Refresh (On-demand)

- Re-fetches skills from database
- Rebuilds all vectors
- Atomically swaps in-memory vectors
- No service restart required

### 4. Model Training (Optional)

The base model matches skills by text similarity. For learned associations (e.g., "MERN Stack" → MongoDB, React), train a custom model:

1. Prepare training data CSV with role-skill mappings
2. Call POST /model/train
3. Model learns to place roles near their associated skills
4. Vectors are automatically rebuilt with trained model

**Training Data Format (CSV):**
```csv
role,skills
"MERN Stack Developer","MongoDB,Express.js,React.js,Node.js,JavaScript"
"Data Scientist","Python,Machine Learning,Pandas,NumPy,SQL,TensorFlow"
```

**Training Process:**
- Uses contrastive learning (MultipleNegativesRankingLoss)
- Each (role, skill) pair is a positive example
- Other skills in batch serve as negatives
- Model learns semantic associations, not just text similarity

**Adding New Skills After Training:**
- Add skill to database
- Call POST /skills/refresh-vectors
- New skill gets embedded with trained model
- No retraining needed (model generalizes)

## Text Normalization

Role text is normalized before matching:

**Noise words removed:**
- senior, junior, lead
- engineer, developer, software
- staff, principal, associate
- intern, trainee, specialist

**Example:**
- Input: "Senior MERN Stack Developer"
- Normalized: "mern stack"

## Database Schema

The service reads from the `skills` table:

| Column | Type | Description |
|--------|------|-------------|
| skill_id | INTEGER | Primary key |
| skill_name | VARCHAR(500) | Skill name |
| skill_type | INTEGER | Skill category |
| createdAt | TIMESTAMPTZ | Creation timestamp |
| updatedAt | TIMESTAMPTZ | Update timestamp |
| curatal_skill | INTEGER | 0=old, 1=active, 2=deactivated |

Only skills with `curatal_skill = 1` are indexed.

## Example cURL Commands

### Suggest Skills

```bash
curl -X POST http://localhost:8000/suggest-skills \
  -H "Content-Type: application/json" \
  -d '{"role": "Senior MERN Stack Developer", "limit": 10}'
```

### Refresh Vectors

```bash
curl -X POST http://localhost:8000/skills/refresh-vectors
```

### Health Check

```bash
curl http://localhost:8000/skills/health
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| DB_NAME | skill_matching | Database name |
| DB_USER | postgres | Database user |
| DB_PASSWORD | postgres | Database password |
| DB_HOST | localhost | Database host |
| DB_PORT | 5433 | Database port |

## Performance Notes

- First startup may take longer due to model download and vectorization
- Subsequent startups load vectors from disk (~seconds)
- Vector refresh runs in background with atomic swap
- Memory usage: ~1.5KB per skill (384 floats × 4 bytes)
