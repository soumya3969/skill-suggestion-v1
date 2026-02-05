# Skill Suggestion System – Technical Design Document

**Version:** 2.0.0  
**Last Updated:** February 2026  
**Status:** Development Phase

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [System Objectives](#2-system-objectives)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Core Components](#5-core-components)
6. [Data Model](#6-data-model)
7. [Training Pipeline](#7-training-pipeline)
8. [Search Methods](#8-search-methods)
9. [System Flow](#9-system-flow)
10. [API Design](#10-api-design)
11. [Concurrency & Safety](#11-concurrency--safety)
12. [Configuration](#12-configuration)
13. [Design Principles](#13-design-principles)
14. [Limitations & Future Improvements](#14-limitations--future-improvements)

---

## 1. Purpose & Scope

This document describes the design and implementation of a **vector-based Skill Suggestion Service** that provides semantic skill recommendations based on job roles or designations.

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Hybrid Search** | Combines direct role-skill mappings with semantic similarity |
| **Trainable Model** | Fine-tune on labeled role-skill pairs for learned associations |
| **Self-hosted** | No external API dependencies |
| **Deterministic** | Explainable, reproducible results |
| **Low Latency** | In-memory vector search for real-time usage |

### What Changed from v1.0

| Version 1.0 | Version 2.0 |
|-------------|-------------|
| Pure semantic similarity | Hybrid search (mapped + semantic) |
| No training capability | Custom model training |
| Text matching only | Learned associations |
| Single search method | Three search methods |

---

## 2. System Objectives

The Skill Suggestion Service aims to:

- ✅ Accept a job role or designation as input
- ✅ Suggest relevant technical skills using semantic similarity
- ✅ Use direct role-skill mappings from training data (NEW)
- ✅ Support custom model training (NEW)
- ✅ Use only active skills from the database (`curatal_skill = 1`)
- ✅ Support explicit vector refresh without restart
- ✅ Operate without external APIs or paid services
- ✅ Provide explainable results with confidence scores and source attribution

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SKILL SUGGESTION SERVICE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   FastAPI       │    │   Role Mapper   │    │   Trainer       │         │
│  │   (API Layer)   │    │   (Direct       │    │   (Fine-tune    │         │
│  │                 │    │    Lookup)      │    │    Model)       │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
│           ▼                      ▼                      ▼                   │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    HYBRID SEARCH ENGINE                          │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │      │
│  │  │  Mapped    │  │  Semantic  │  │  Combined  │                 │      │
│  │  │  Search    │→ │  Search    │→ │  Results   │                 │      │
│  │  └────────────┘  └────────────┘  └────────────┘                 │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│           │                      │                                          │
│           ▼                      ▼                                          │
│  ┌─────────────────┐    ┌─────────────────┐                                │
│  │   Vectorizer    │    │   Local Files   │                                │
│  │   (Embeddings)  │    │   (.npy)        │                                │
│  └────────┬────────┘    └─────────────────┘                                │
│           │                                                                 │
└───────────┼─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POSTGRESQL (Read-Only)                               │
│                        skill_taxonamy table                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Logical Components

| Component | Responsibility |
|-----------|----------------|
| **FastAPI** | REST API exposure, validation, request handling |
| **Role Mapper** | Direct lookup from training data (CSV) |
| **Trainer** | Fine-tune sentence-transformer on role-skill pairs |
| **Hybrid Search Engine** | Combine mapped + semantic results |
| **Vectorizer** | Generate embeddings using sentence-transformers |
| **PostgreSQL** | Source of truth for skill taxonomy (read-only) |

---

## 4. Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.9+ | Runtime |
| FastAPI | ≥0.109.0 | REST API framework |
| sentence-transformers | ≥2.6.1 | Embedding generation & training |
| NumPy | ≥2.0.0 | Vector operations |
| Pandas | ≥2.2.0 | Data processing |
| psycopg2 | ≥2.9.9 | PostgreSQL driver |
| datasets | ≥2.14.0 | Training data handling |
| accelerate | ≥1.1.0 | Training optimization |

### Storage

| Storage | Purpose |
|---------|---------|
| PostgreSQL | Skill taxonomy (read-only) |
| Local `.npy` files | Vector storage |
| Local `models/` directory | Trained model storage |
| Local `training_data/` directory | Training CSV files |

### Model

| Model | Description |
|-------|-------------|
| Base Model | `all-MiniLM-L6-v2` (384-dimensional embeddings) |
| Trained Model | Fine-tuned version saved in `models/skill-matcher-v1/` |

---

## 5. Core Components

### 5.1 Project Structure

```
skill_suggest_v1/
├── api/
│   ├── __init__.py
│   ├── suggest.py          # POST /suggest-skills
│   ├── refresh.py          # POST /skills/refresh-vectors, GET /skills/health
│   └── train.py            # POST /model/train, GET /model/status, etc.
├── core/
│   ├── __init__.py
│   ├── db.py               # PostgreSQL connection & queries
│   ├── normalizer.py       # Text normalization
│   ├── role_mapper.py      # Direct role-skill mapping
│   ├── similarity.py       # Hybrid search engine
│   ├── trainer.py          # Model fine-tuning
│   └── vectorizer.py       # Embedding generation
├── data/
│   ├── skill_vectors.npy   # Skill embeddings (generated)
│   └── skill_ids.npy       # Skill ID mapping (generated)
├── models/
│   └── skill-matcher-v1/   # Trained model (generated)
├── training_data/
│   └── role_skills.csv     # Training data
├── docs/
│   └── TECHNICAL_DESIGN_DOCUMENT.md
├── app.py                  # FastAPI application
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### 5.2 Component Responsibilities

#### FastAPI (api/)

**Responsible for:**
- Exposing REST APIs
- Input validation and normalization
- Error handling and HTTP responses
- Request routing

**Does NOT:**
- Create, update, or deactivate skills
- Apply business rules
- Persist data to database

#### Core Modules (core/)

| Module | Responsibility |
|--------|----------------|
| `db.py` | PostgreSQL connection, fetch active skills |
| `normalizer.py` | Text normalization, noise word removal |
| `role_mapper.py` | Load CSV, exact/fuzzy role matching |
| `similarity.py` | Hybrid search, cosine similarity |
| `trainer.py` | Contrastive learning, model fine-tuning |
| `vectorizer.py` | Embedding generation, model loading |

#### PostgreSQL

**Responsible for:**
- Storing skill taxonomy
- Indicating skill lifecycle via `curatal_skill`

**Does NOT:**
- Store vectors
- Perform similarity search
- Participate in inference runtime

---

## 6. Data Model

### 6.1 Database Table: `skill_taxonamy`

| Column | Type | Description |
|--------|------|-------------|
| `skill_id` | INTEGER (PK) | Unique skill identifier |
| `skill_name` | VARCHAR(500) | Skill display name |
| `skill_type` | INTEGER | Classification type |
| `createdAt` | TIMESTAMPTZ | Creation timestamp |
| `updatedAt` | TIMESTAMPTZ | Last update timestamp |
| `curatal_skill` | INTEGER | Skill lifecycle state |

**curatal_skill values:**
- `0` = Old/migrated skills
- `1` = Active skill (only these are vectorized)
- `2` = Deactivated skill

### 6.2 Training Data Format (CSV)

```csv
role,skills
"MERN Stack Developer","MongoDB,Express.js,React.js,Node.js,JavaScript,REST API"
"Data Scientist","Python,Machine Learning,Pandas,NumPy,SQL,TensorFlow"
"Java Full Stack Developer","Java,Spring Boot,Hibernate,Angular,MySQL"
```

| Column | Description |
|--------|-------------|
| `role` | Job role or designation |
| `skills` | Comma-separated list of associated skills |

### 6.3 Vector Storage

| File | Content | Shape |
|------|---------|-------|
| `skill_vectors.npy` | L2-normalized embeddings | (n_skills, 384) |
| `skill_ids.npy` | Skill ID mapping | (n_skills,) |

---

## 7. Training Pipeline

### 7.1 Overview

The training pipeline fine-tunes the base sentence-transformer model to learn role-skill associations using contrastive learning.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Training Data  │ ──▶ │  Create Pairs   │ ──▶ │  Fine-tune      │
│  (CSV)          │     │  (role, skill)  │     │  Model          │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Refresh        │ ◀── │  Save Model     │ ◀── │  Contrastive    │
│  Vectors        │     │  Locally        │     │  Loss           │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 7.2 Training Process

1. **Load Training Data**
   - Read CSV file with role-skill mappings
   - Parse comma-separated skills

2. **Create Training Examples**
   - Each (role, skill) pair becomes one training example
   - Example: "MERN Stack Developer" + "MongoDB" = 1 pair

3. **Fine-tune Model**
   - Use `MultipleNegativesRankingLoss`
   - Other skills in batch serve as negatives
   - Model learns to place roles close to associated skills

4. **Save Model**
   - Model saved to `models/skill-matcher-v1/`

5. **Refresh Vectors**
   - Re-embed all skills with trained model
   - Update in-memory vectors

### 7.3 Training Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `epochs` | 10 | Number of training epochs |
| `batch_size` | 16 | Training batch size |
| `warmup_steps` | 100 | Learning rate warmup |
| `base_model` | all-MiniLM-L6-v2 | Base sentence-transformer |

### 7.4 Loss Function

**MultipleNegativesRankingLoss:**
- For each (anchor, positive) pair in batch
- Other positives serve as in-batch negatives
- Pulls anchor (role) close to positive (associated skill)
- Pushes anchor away from negatives (unrelated skills)

---

## 8. Search Methods

### 8.1 Three Search Methods

| Method | Description | When Used |
|--------|-------------|-----------|
| `mapped` | Direct lookup from training data | Role matches training data exactly/fuzzy |
| `semantic` | Vector similarity search | Role not in training data |
| `hybrid` | Mapped + semantic combined | Partial match, supplement with semantic |

### 8.2 Hybrid Search Flow

```
Input: "Senior MERN Stack Developer"
            │
            ▼
┌───────────────────────────┐
│ 1. Normalize Role         │
│    → "mern stack"         │
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│ 2. Check Role Mapper      │
│    Exact match? ✗         │
│    Fuzzy match? ✓ (0.85)  │
│    → "mern stack"         │
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│ 3. Get Mapped Skills      │
│    MongoDB, Express.js,   │
│    React.js, Node.js...   │
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│ 4. Find in Database       │
│    Fuzzy match skill      │
│    names to DB records    │
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│ 5. Supplement with        │
│    Semantic Search        │
│    (if needed)            │
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│ 6. Return Combined        │
│    Results with source    │
│    attribution            │
└───────────────────────────┘
```

### 8.3 Role Normalization

**Noise words removed:**
```
senior, junior, lead, engineer, developer, software,
staff, principal, associate, intern, trainee, specialist,
consultant, analyst, architect, manager, head, chief, vp, director
```

**Example:**
- Input: `"Senior MERN Stack Developer"`
- Output: `"mern stack"`

### 8.4 Similarity Threshold

- **Default threshold:** 0.45
- Skills with similarity below threshold are filtered out
- Mapped skills get confidence based on fuzzy match score

---

## 9. System Flow

### 9.1 Startup Flow

```
1. Load environment variables
2. Validate DB connection parameters
3. Initialize Search Engine
   a. Check for existing vectors on disk
   b. If exists: load into memory
   c. If not: fetch skills from DB, vectorize, save, load
4. Initialize Role Mapper
   a. Load training CSV
   b. Build role-skill lookup table
5. Ready to serve requests
```

### 9.2 Suggestion Flow

```
1. Receive POST /suggest-skills request
2. Validate input (role, limit)
3. Normalize role text
4. Hybrid Search:
   a. Check role mapper for direct mapping
   b. If found: lookup skills in DB by name
   c. If partial/none: run semantic search
   d. Combine results, deduplicate
5. Return response with:
   - normalized_role
   - skills (with confidence and source)
   - search_method used
```

### 9.3 Training Flow

```
1. Receive POST /model/train request
2. Unload existing model from memory
3. Load training data from CSV
4. Create (role, skill) training pairs
5. Load base model
6. Fine-tune with contrastive loss
7. Save trained model to temp directory
8. Move to final location (avoid file locking)
9. Refresh skill vectors with new model
10. Reload role mapper
11. Return training results
```

### 9.4 Refresh Flow

```
1. Receive POST /skills/refresh-vectors request
2. Re-fetch active skills from DB
3. Rebuild vectors using current model
4. Save to disk atomically
5. Swap in-memory vectors (thread-safe)
6. Return refresh results
```

---

## 10. API Design

### 10.1 Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/suggest-skills` | Suggest skills for a role |
| POST | `/skills/refresh-vectors` | Rebuild vectors from DB |
| GET | `/skills/health` | Service health check |
| POST | `/model/train` | Train custom model |
| GET | `/model/status` | Model status info |
| POST | `/model/upload-training-data` | Upload training CSV |
| GET | `/model/training-files` | List training files |
| DELETE | `/model/trained` | Delete trained model |

### 10.2 POST /suggest-skills

**Request:**
```json
{
  "role": "Senior MERN Stack Developer",
  "limit": 10,
  "use_mapping": true
}
```

**Response:**
```json
{
  "normalized_role": "mern stack",
  "search_method": "mapped",
  "skills": [
    {
      "skill_id": 12345,
      "skill_name": "MongoDB",
      "confidence": 0.95,
      "source": "mapped"
    },
    {
      "skill_id": 12346,
      "skill_name": "React.js",
      "confidence": 0.95,
      "source": "mapped"
    }
  ]
}
```

### 10.3 POST /model/train

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
  "training_pairs": 280,
  "epochs": 10,
  "message": "Successfully trained model on 280 pairs"
}
```

### 10.4 GET /model/status

**Response:**
```json
{
  "trained_model_exists": true,
  "model_path": "models/skill-matcher-v1",
  "skills_indexed": 6847,
  "using_trained_model": true,
  "role_mappings_loaded": 35
}
```

---

## 11. Concurrency & Safety

### 11.1 Thread Safety

| Component | Mechanism |
|-----------|-----------|
| Vector refresh | `RLock` for atomic swap |
| Model reload | Garbage collection before file operations |
| DB connections | Context manager (auto-close) |

### 11.2 File Locking (Windows)

**Problem:** Windows locks files that are memory-mapped by PyTorch.

**Solution:**
1. Unload model from memory before training
2. Save to temporary directory first
3. Move/rename to final location
4. Garbage collect to release handles

### 11.3 Atomic Operations

- Vector files saved atomically (temp file + rename)
- In-memory vectors swapped under lock
- No partial state exposure

---

## 12. Configuration

### 12.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_NAME` | Database name | - |
| `DB_USER` | Database user | - |
| `DB_PASSWORD` | Database password | - |
| `DB_HOST` | Database host | localhost |
| `DB_PORT` | Database port | 5432 |

### 12.2 Constants

| Constant | Value | Location |
|----------|-------|----------|
| `SIMILARITY_THRESHOLD` | 0.45 | `core/similarity.py` |
| `MAPPED_SKILL_CONFIDENCE` | 0.95 | `core/similarity.py` |
| `FUZZY_THRESHOLD` | 0.7 | `core/role_mapper.py` |
| `DEFAULT_EPOCHS` | 10 | `core/trainer.py` |
| `DEFAULT_BATCH_SIZE` | 16 | `core/trainer.py` |
| `EMBEDDING_DIMENSION` | 384 | `core/vectorizer.py` |

---

## 13. Design Principles

### 13.1 Core Principles

| Principle | Implementation |
|-----------|----------------|
| **Hybrid over pure semantic** | Use mappings when available, fallback to semantic |
| **Deterministic** | Same input → same output |
| **Explainable** | Source attribution for each result |
| **Explicit refresh** | No automatic retraining |
| **Single responsibility** | Each module has one job |
| **Database as truth** | PostgreSQL is source of truth for skills |
| **Vectors for speed** | In-memory search for low latency |

### 13.2 What the System Avoids

- ❌ Hardcoded skill mappings (except training data)
- ❌ External API dependencies
- ❌ Database vector storage
- ❌ Black-box decisions
- ❌ Automatic retraining
- ❌ Writes to production database

---

## 14. Limitations & Future Improvements

### 14.1 Current Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Fuzzy matching threshold | May miss some role matches | Tune threshold per use case |
| Training data quality | Model quality depends on data | Curate training data carefully |
| CPU-only training | Slower training (~40s for 300 pairs) | Use GPU if available |
| Single language | English only | Add multilingual support |

### 14.2 Future Improvements

| Improvement | Description | Priority |
|-------------|-------------|----------|
| GPU support | Faster training and inference | Medium |
| Batch inference | Process multiple roles in one call | Low |
| Confidence calibration | Better probability estimates | Medium |
| A/B testing | Compare model versions | Low |
| Skill clustering | Group related skills | Low |

---

## Appendix A: Mental Model

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   PostgreSQL stores TRUTH (what skills exist)                   │
│                                                                 │
│   Training Data stores KNOWLEDGE (what skills go with roles)    │
│                                                                 │
│   Python UNDERSTANDS meaning (embeddings)                       │
│                                                                 │
│   Vectors enable SPEED (in-memory search)                       │
│                                                                 │
│   Hybrid search provides ACCURACY (best of both worlds)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Quick Reference

### Start Service
```bash
uvicorn app:app --reload
```

### Train Model
```bash
curl -X POST http://localhost:8000/model/train \
  -H "Content-Type: application/json" \
  -d '{"epochs": 10}'
```

### Suggest Skills
```bash
curl -X POST http://localhost:8000/suggest-skills \
  -H "Content-Type: application/json" \
  -d '{"role": "MERN Stack Developer", "limit": 10}'
```

### Refresh Vectors
```bash
curl -X POST http://localhost:8000/skills/refresh-vectors
```

---

**Document End**
