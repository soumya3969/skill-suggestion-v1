/**
 * API Service Layer
 * Centralized API calls with error handling
 */

const API_BASE = '/api';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
      throw new Error('Unable to connect to server. Please ensure the backend is running.');
    }
    throw error;
  }
}

// ============================================
// Skill Suggestion APIs
// ============================================

/**
 * Suggest skills for a given role
 * @param {string} role - Job role/designation
 * @param {number} limit - Max results (default 10)
 * @param {boolean} useMapping - Use role-skill mappings (default true)
 */
export async function suggestSkills(role, limit = 10, useMapping = true) {
  return fetchApi('/suggest-skills', {
    method: 'POST',
    body: JSON.stringify({
      role,
      limit,
      use_mapping: useMapping,
    }),
  });
}

// ============================================
// Vector Management APIs
// ============================================

/**
 * Refresh skill vectors from database
 * @param {boolean} reloadModel - Reload embedding model
 */
export async function refreshVectors(reloadModel = false) {
  return fetchApi('/skills/refresh-vectors', {
    method: 'POST',
    body: JSON.stringify({ reload_model: reloadModel }),
  });
}

/**
 * Get service health status
 */
export async function getHealth() {
  return fetchApi('/skills/health');
}

// ============================================
// Model Management APIs
// ============================================

/**
 * Get model status
 */
export async function getModelStatus() {
  return fetchApi('/model/status');
}

/**
 * Train model on role-skill pairs
 * @param {string} trainingFile - CSV filename
 * @param {number} epochs - Training epochs
 * @param {number} batchSize - Batch size
 */
export async function trainModel(trainingFile = 'role_skills.csv', epochs = 10, batchSize = 16) {
  return fetchApi('/model/train', {
    method: 'POST',
    body: JSON.stringify({
      training_file: trainingFile,
      epochs,
      batch_size: batchSize,
    }),
  });
}

/**
 * Delete trained model
 */
export async function deleteTrainedModel() {
  return fetchApi('/model/trained', {
    method: 'DELETE',
  });
}

/**
 * List available training files
 */
export async function getTrainingFiles() {
  return fetchApi('/model/training-files');
}

/**
 * Upload training data CSV
 * @param {File} file - CSV file to upload
 * @param {string} filename - Optional custom filename
 */
export async function uploadTrainingData(file, filename = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (filename) {
    formData.append('filename', filename);
  }

  const url = `${API_BASE}/model/upload-training-data`;
  
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

// ============================================
// Knowledge Base APIs (Training Data)
// ============================================

/**
 * Get role-skill mappings from training data
 * This fetches the CSV content via a custom endpoint we'll need
 */
export async function getRoleMappings() {
  return fetchApi('/knowledge-base/mappings');
}

/**
 * Add a new role-skill mapping
 */
export async function addRoleMapping(role, skills) {
  return fetchApi('/knowledge-base/mappings', {
    method: 'POST',
    body: JSON.stringify({ role, skills }),
  });
}

/**
 * Update an existing role-skill mapping
 */
export async function updateRoleMapping(originalRole, role, skills) {
  return fetchApi('/knowledge-base/mappings', {
    method: 'PUT',
    body: JSON.stringify({ original_role: originalRole, role, skills }),
  });
}

/**
 * Delete a role-skill mapping
 */
export async function deleteRoleMapping(role) {
  return fetchApi(`/knowledge-base/mappings/${encodeURIComponent(role)}`, {
    method: 'DELETE',
  });
}
