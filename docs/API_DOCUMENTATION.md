# Skill Suggestion Service – API Documentation

**Version:** 2.0.0  
**Base URL:** `http://localhost:8000`  
**Documentation:** `/docs` (Swagger UI), `/redoc` (ReDoc)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Error Handling](#error-handling)
4. [Skill Suggestion APIs](#skill-suggestion-apis)
5. [Vector Management APIs](#vector-management-apis)
6. [Model Training APIs](#model-training-apis)

---

## Overview

The Skill Suggestion Service provides a REST API for suggesting relevant technical skills based on job roles or designations. It uses a hybrid approach combining direct role-skill mappings with semantic similarity search.

### Base Information

| Property | Value |
|----------|-------|
| Protocol | HTTP/HTTPS |
| Format | JSON |
| Encoding | UTF-8 |
| Content-Type | `application/json` |

### API Categories

| Category | Description |
|----------|-------------|
| **Skill Suggestion** | Suggest skills for a given role |
| **Vector Management** | Refresh and manage skill vectors |
| **Model Training** | Train and manage custom models |

---

## Authentication

Currently, no authentication is required. For production deployments, implement appropriate authentication mechanisms (API keys, OAuth2, etc.).

---

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad Request - Invalid input |
| `404` | Not Found - Resource doesn't exist |
| `422` | Unprocessable Entity - Validation error |
| `500` | Internal Server Error |
| `503` | Service Unavailable - Not initialized |

### Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

### Validation Error Format

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error description",
      "type": "error_type"
    }
  ]
}
```

---

## Skill Suggestion APIs

### POST /suggest-skills

Suggest relevant skills for a given job role using hybrid search.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "role": "Senior MERN Stack Developer",
  "limit": 10,
  "use_mapping": true
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `role` | string | Yes | - | Job role or designation (1-500 chars) |
| `limit` | integer | No | 10 | Max skills to return (1-50) |
| `use_mapping` | boolean | No | true | Use role-skill mappings from training data |

#### Response

**Success (200):**
```json
{
  "normalized_role": "mern stack",
  "search_method": "mapped",
  "skills": [
    {
      "skill_id": 15241,
      "skill_name": "MongoDB",
      "confidence": 0.95,
      "source": "mapped"
    },
    {
      "skill_id": 15242,
      "skill_name": "React.js",
      "confidence": 0.95,
      "source": "mapped"
    },
    {
      "skill_id": 15243,
      "skill_name": "Express.js",
      "confidence": 0.95,
      "source": "mapped"
    },
    {
      "skill_id": 15244,
      "skill_name": "Node.js",
      "confidence": 0.95,
      "source": "mapped"
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `normalized_role` | string | Role after noise word removal |
| `search_method` | string | Method used: `mapped`, `semantic`, or `hybrid` |
| `skills` | array | List of matching skills |
| `skills[].skill_id` | integer | Database skill ID |
| `skills[].skill_name` | string | Skill display name |
| `skills[].confidence` | float | Similarity score (0-1) |
| `skills[].source` | string | Result source: `mapped` or `semantic` |

**Search Methods:**

| Method | Description |
|--------|-------------|
| `mapped` | All results from role-skill mappings |
| `semantic` | All results from vector similarity |
| `hybrid` | Mixed results from both sources |

#### Examples

**Example 1: Known Role (Mapped)**
```bash
curl -X POST http://localhost:8000/suggest-skills \
  -H "Content-Type: application/json" \
  -d '{
    "role": "MERN Stack Developer",
    "limit": 10
  }'
```

**Example 2: Unknown Role (Semantic)**
```bash
curl -X POST http://localhost:8000/suggest-skills \
  -H "Content-Type: application/json" \
  -d '{
    "role": "GraphQL API Specialist",
    "limit": 5
  }'
```

**Example 3: Disable Mapping**
```bash
curl -X POST http://localhost:8000/suggest-skills \
  -H "Content-Type: application/json" \
  -d '{
    "role": "MERN Stack Developer",
    "limit": 10,
    "use_mapping": false
  }'
```

---

## Vector Management APIs

### POST /skills/refresh-vectors

Rebuild skill vectors from the database.

#### Description

- Re-fetches all active skills (`curatal_skill = 1`) from database
- Rebuilds vector embeddings using current model
- Atomically swaps in-memory vectors
- Thread-safe operation

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "reload_model": false
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `reload_model` | boolean | No | false | Reload the embedding model before refresh |

#### Response

**Success (200):**
```json
{
  "success": true,
  "skills_indexed": 6847,
  "message": "Successfully refreshed vectors for 6847 skills"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation success status |
| `skills_indexed` | integer | Number of skills vectorized |
| `message` | string | Human-readable result message |

#### Example

```bash
curl -X POST http://localhost:8000/skills/refresh-vectors \
  -H "Content-Type: application/json" \
  -d '{"reload_model": true}'
```

---

### GET /skills/health

Check service health and readiness.

#### Response

**Success (200):**
```json
{
  "status": "healthy",
  "skills_indexed": 6847,
  "vectors_loaded": true,
  "model_loaded": true
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Service status (`healthy` or `unhealthy`) |
| `skills_indexed` | integer | Number of indexed skills |
| `vectors_loaded` | boolean | Vectors in memory |
| `model_loaded` | boolean | Embedding model loaded |

#### Example

```bash
curl http://localhost:8000/skills/health
```

---

## Model Training APIs

### POST /model/train

Train a custom skill suggestion model.

#### Description

Fine-tunes the base sentence-transformer model on role-skill pairs using contrastive learning.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "training_file": "role_skills.csv",
  "epochs": 10,
  "batch_size": 16
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `training_file` | string | No | `role_skills.csv` | CSV file name in `training_data/` |
| `epochs` | integer | No | 10 | Number of training epochs (1-100) |
| `batch_size` | integer | No | 16 | Batch size (2-128) |

#### Response

**Success (200):**
```json
{
  "success": true,
  "model_path": "models/skill-matcher-v1",
  "training_pairs": 280,
  "epochs": 10,
  "message": "Successfully trained model on 280 role-skill pairs for 10 epochs"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Training success status |
| `model_path` | string | Path to saved model |
| `training_pairs` | integer | Number of training examples |
| `epochs` | integer | Epochs completed |
| `message` | string | Human-readable result |

#### Training Data Format

CSV file with columns:
- `role`: Job role or designation
- `skills`: Comma-separated list of skills

```csv
role,skills
"MERN Stack Developer","MongoDB,Express.js,React.js,Node.js,JavaScript"
"Data Scientist","Python,Machine Learning,Pandas,NumPy,SQL"
```

#### Example

```bash
curl -X POST http://localhost:8000/model/train \
  -H "Content-Type: application/json" \
  -d '{
    "training_file": "role_skills.csv",
    "epochs": 15,
    "batch_size": 16
  }'
```

---

### GET /model/status

Get current model status and statistics.

#### Response

**Success (200):**
```json
{
  "trained_model_exists": true,
  "model_path": "models/skill-matcher-v1",
  "skills_indexed": 6847,
  "using_trained_model": true,
  "role_mappings_loaded": 35
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `trained_model_exists` | boolean | Custom model available |
| `model_path` | string | Path to trained model |
| `skills_indexed` | integer | Skills in vector index |
| `using_trained_model` | boolean | Currently using trained model |
| `role_mappings_loaded` | integer | Role-skill mappings loaded |

#### Example

```bash
curl http://localhost:8000/model/status
```

---

### POST /model/upload-training-data

Upload a new training data CSV file.

#### Request

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | CSV file with role,skills columns |
| `filename` | string | No | Custom filename (default: uploaded name) |

#### Response

**Success (200):**
```json
{
  "success": true,
  "filename": "custom_training.csv",
  "path": "training_data/custom_training.csv",
  "message": "Successfully uploaded training data"
}
```

#### Example

```bash
curl -X POST http://localhost:8000/model/upload-training-data \
  -F "file=@my_training_data.csv" \
  -F "filename=custom_training.csv"
```

---

### GET /model/training-files

List available training data files.

#### Response

**Success (200):**
```json
{
  "files": [
    {
      "name": "role_skills.csv",
      "path": "training_data/role_skills.csv",
      "size_bytes": 2048
    }
  ],
  "count": 1
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `files` | array | List of training files |
| `files[].name` | string | Filename |
| `files[].path` | string | Relative path |
| `files[].size_bytes` | integer | File size |
| `count` | integer | Total file count |

#### Example

```bash
curl http://localhost:8000/model/training-files
```

---

### DELETE /model/trained

Delete the trained model and revert to base model.

#### Response

**Success (200):**
```json
{
  "success": true,
  "message": "Trained model deleted. Service reverted to base model."
}
```

**Not Found (404):**
```json
{
  "detail": "No trained model exists"
}
```

#### Example

```bash
curl -X DELETE http://localhost:8000/model/trained
```

---

## Rate Limits

Currently no rate limits are enforced. For production:
- Consider 100 requests/minute per IP for suggestion endpoints
- Consider 1 request/minute for training endpoint

---

## Changelog

### Version 2.0.0
- Added hybrid search (mapped + semantic)
- Added model training endpoints
- Added training data upload
- Added source attribution in responses
- Added search_method field

### Version 1.0.0
- Initial release
- Semantic similarity search
- Vector refresh endpoint

---

**Documentation End**
