import { useState, useEffect, useCallback } from 'react';
import { 
  getModelStatus, 
  getHealth, 
  refreshVectors, 
  trainModel,
  getTrainingFiles,
  uploadTrainingData,
  deleteTrainedModel,
  getRoleMappings,
  addRoleMapping,
  updateRoleMapping,
  deleteRoleMapping
} from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import './KnowledgeBase.css';

function KnowledgeBase() {
  // System status
  const [health, setHealth] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [trainingFiles, setTrainingFiles] = useState([]);
  
  // Role mappings
  const [mappings, setMappings] = useState([]);
  const [mappingsLoading, setMappingsLoading] = useState(true);
  const [mappingsError, setMappingsError] = useState(null);
  
  // UI state
  const [activeTab, setActiveTab] = useState('mappings');
  const [refreshing, setRefreshing] = useState(false);
  const [training, setTraining] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState('add'); // 'add' or 'edit'
  const [editingMapping, setEditingMapping] = useState(null);
  const [formData, setFormData] = useState({ role: '', skills: '' });
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  
  // Training form
  const [trainConfig, setTrainConfig] = useState({
    file: 'role_skills.csv',
    epochs: 10,
    batchSize: 16
  });
  
  // Fetch initial data
  useEffect(() => {
    fetchSystemStatus();
    fetchMappings();
  }, []);
  
  const fetchSystemStatus = async () => {
    try {
      const [healthData, statusData, filesData] = await Promise.all([
        getHealth().catch(() => null),
        getModelStatus().catch(() => null),
        getTrainingFiles().catch(() => ({ files: [] }))
      ]);
      
      setHealth(healthData);
      setModelStatus(statusData);
      setTrainingFiles(filesData.files || []);
    } catch (err) {
      console.error('Failed to fetch system status:', err);
    }
  };
  
  const fetchMappings = async () => {
    setMappingsLoading(true);
    setMappingsError(null);
    
    try {
      const data = await getRoleMappings();
      setMappings(data.mappings || []);
    } catch (err) {
      setMappingsError(err.message);
      setMappings([]);
    } finally {
      setMappingsLoading(false);
    }
  };
  
  // Actions
  const handleRefresh = async () => {
    setRefreshing(true);
    setActionMessage(null);
    
    try {
      const result = await refreshVectors(true);
      setActionMessage({
        type: 'success',
        text: `Successfully refreshed ${result.skills_indexed} skills`
      });
      await fetchSystemStatus();
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.message
      });
    } finally {
      setRefreshing(false);
    }
  };
  
  const handleTrain = async () => {
    setTraining(true);
    setActionMessage(null);
    
    try {
      const result = await trainModel(
        trainConfig.file, 
        trainConfig.epochs, 
        trainConfig.batchSize
      );
      setActionMessage({
        type: 'success',
        text: `Training complete! ${result.training_pairs} pairs trained for ${result.epochs} epochs`
      });
      await fetchSystemStatus();
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: `Training failed: ${err.message}`
      });
    } finally {
      setTraining(false);
    }
  };
  
  const handleDeleteModel = async () => {
    if (!confirm('Are you sure you want to delete the trained model? This will revert to the base model.')) {
      return;
    }
    
    try {
      await deleteTrainedModel();
      setActionMessage({
        type: 'success',
        text: 'Trained model deleted. Service reverted to base model.'
      });
      await fetchSystemStatus();
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.message
      });
    }
  };
  
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    try {
      await uploadTrainingData(file);
      setActionMessage({
        type: 'success',
        text: `Successfully uploaded ${file.name}`
      });
      await fetchSystemStatus();
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.message
      });
    }
    
    e.target.value = '';
  };
  
  // Modal handlers
  const openAddModal = () => {
    setModalMode('add');
    setFormData({ role: '', skills: '' });
    setFormError(null);
    setShowModal(true);
  };
  
  const openEditModal = (mapping) => {
    setModalMode('edit');
    setEditingMapping(mapping);
    setFormData({
      role: mapping.role,
      skills: mapping.skills.join(', ')
    });
    setFormError(null);
    setShowModal(true);
  };
  
  const closeModal = () => {
    setShowModal(false);
    setEditingMapping(null);
    setFormError(null);
  };
  
  const handleFormSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    
    const role = formData.role.trim();
    const skills = formData.skills
      .split(',')
      .map(s => s.trim())
      .filter(s => s.length > 0);
    
    if (!role) {
      setFormError('Role is required');
      return;
    }
    
    if (skills.length === 0) {
      setFormError('At least one skill is required');
      return;
    }
    
    setSubmitting(true);
    
    try {
      if (modalMode === 'add') {
        await addRoleMapping(role, skills);
      } else {
        await updateRoleMapping(editingMapping.role, role, skills);
      }
      
      closeModal();
      await fetchMappings();
      setActionMessage({
        type: 'success',
        text: modalMode === 'add' ? 'Mapping added successfully' : 'Mapping updated successfully'
      });
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleDeleteMapping = async (role) => {
    if (!confirm(`Delete mapping for "${role}"?`)) {
      return;
    }
    
    try {
      await deleteRoleMapping(role);
      await fetchMappings();
      setActionMessage({
        type: 'success',
        text: 'Mapping deleted successfully'
      });
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err.message
      });
    }
  };
  
  return (
    <div className="kb-page">
      {/* Header */}
      <div className="kb-header">
        <div className="kb-header-content">
          <h1 className="kb-title">Knowledge Base Management</h1>
          <p className="kb-subtitle">Manage role-skill mappings, train models, and monitor system status</p>
        </div>
      </div>
      
      {/* Action Message */}
      {actionMessage && (
        <div className={`action-message ${actionMessage.type}`}>
          <span>{actionMessage.text}</span>
          <button onClick={() => setActionMessage(null)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}
      
      {/* Tabs */}
      <div className="kb-tabs">
        <button 
          className={`tab-button ${activeTab === 'mappings' ? 'active' : ''}`}
          onClick={() => setActiveTab('mappings')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          Role Mappings
        </button>
        <button 
          className={`tab-button ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          System & Training
        </button>
      </div>
      
      {/* Content */}
      <div className="kb-content">
        {/* Mappings Tab */}
        {activeTab === 'mappings' && (
          <div className="mappings-section">
            <div className="section-header">
              <h2>Role-Skill Mappings</h2>
              <button className="btn-primary" onClick={openAddModal}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Add Mapping
              </button>
            </div>
            
            {mappingsLoading ? (
              <div className="loading-state">
                <LoadingSpinner text="Loading mappings..." />
              </div>
            ) : mappingsError ? (
              <div className="error-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <p>{mappingsError}</p>
                <button className="btn-secondary" onClick={fetchMappings}>Retry</button>
              </div>
            ) : mappings.length === 0 ? (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
                <p>No role mappings found</p>
                <span>Add your first mapping or upload training data</span>
              </div>
            ) : (
              <div className="mappings-table-container">
                <table className="mappings-table">
                  <thead>
                    <tr>
                      <th>Role</th>
                      <th>Skills</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mappings.map((mapping, index) => (
                      <tr key={index}>
                        <td className="role-cell">{mapping.role}</td>
                        <td className="skills-cell">
                          <div className="skill-tags">
                            {mapping.skills.map((skill, i) => (
                              <span key={i} className="skill-tag">{skill}</span>
                            ))}
                          </div>
                        </td>
                        <td className="actions-cell">
                          <button 
                            className="btn-icon" 
                            title="Edit"
                            onClick={() => openEditModal(mapping)}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                            </svg>
                          </button>
                          <button 
                            className="btn-icon danger" 
                            title="Delete"
                            onClick={() => handleDeleteMapping(mapping.role)}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
        
        {/* System Tab */}
        {activeTab === 'system' && (
          <div className="system-section">
            {/* Status Cards */}
            <div className="status-cards">
              <div className="status-card">
                <div className="status-card-header">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                  </svg>
                  <h3>Service Health</h3>
                </div>
                <div className="status-card-body">
                  <div className={`status-badge ${health?.status === 'healthy' ? 'healthy' : 'unhealthy'}`}>
                    {health?.status || 'Unknown'}
                  </div>
                  <div className="status-stats">
                    <div className="stat">
                      <span className="stat-value">{health?.skills_loaded?.toLocaleString() || '—'}</span>
                      <span className="stat-label">Skills Indexed</span>
                    </div>
                    <div className="stat">
                      <span className="stat-value">{health?.vectors_loaded ? 'Yes' : 'No'}</span>
                      <span className="stat-label">Vectors Loaded</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="status-card">
                <div className="status-card-header">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" />
                    <path d="M2 17l10 5 10-5" />
                    <path d="M2 12l10 5 10-5" />
                  </svg>
                  <h3>Model Status</h3>
                </div>
                <div className="status-card-body">
                  <div className={`status-badge ${modelStatus?.trained_model_exists ? 'trained' : 'base'}`}>
                    {modelStatus?.trained_model_exists ? 'Custom Model' : 'Base Model'}
                  </div>
                  <div className="status-stats">
                    <div className="stat">
                      <span className="stat-value">{modelStatus?.role_mappings_loaded || '—'}</span>
                      <span className="stat-label">Role Mappings</span>
                    </div>
                    <div className="stat">
                      <span className="stat-value">{modelStatus?.using_trained_model ? 'Yes' : 'No'}</span>
                      <span className="stat-label">Using Trained</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Actions */}
            <div className="action-cards">
              <div className="action-card">
                <h3>Refresh Vectors</h3>
                <p>Rebuild skill vectors from the database. Use after adding new skills.</p>
                <button 
                  className="btn-primary" 
                  onClick={handleRefresh}
                  disabled={refreshing}
                >
                  {refreshing ? (
                    <>
                      <LoadingSpinner size="small" />
                      Refreshing...
                    </>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M23 4v6h-6" />
                        <path d="M1 20v-6h6" />
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                      </svg>
                      Refresh Vectors
                    </>
                  )}
                </button>
              </div>
              
              <div className="action-card">
                <h3>Train Model</h3>
                <p>Fine-tune the model on role-skill mappings for better suggestions.</p>
                <div className="train-config">
                  <div className="config-row">
                    <label>Training File:</label>
                    <select 
                      value={trainConfig.filename}
                      onChange={(e) => setTrainConfig(prev => ({ ...prev, file: e.target.value }))}
                    >
                      {trainingFiles.map((f, i) => (
                        <option key={i} value={f.filename}>{f.filename}</option>
                      ))}
                    </select>
                  </div>
                  <div className="config-row">
                    <label>Epochs:</label>
                    <input 
                      type="number" 
                      min="1" 
                      max="100"
                      value={trainConfig.epochs}
                      onChange={(e) => setTrainConfig(prev => ({ ...prev, epochs: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="config-row">
                    <label>Batch Size:</label>
                    <input 
                      type="number" 
                      min="2" 
                      max="128"
                      value={trainConfig.batchSize}
                      onChange={(e) => setTrainConfig(prev => ({ ...prev, batchSize: Number(e.target.value) }))}
                    />
                  </div>
                </div>
                <button 
                  className="btn-primary" 
                  onClick={handleTrain}
                  disabled={training}
                >
                  {training ? (
                    <>
                      <LoadingSpinner size="small" />
                      Training...
                    </>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                      Start Training
                    </>
                  )}
                </button>
              </div>
              
              <div className="action-card">
                <h3>Upload Training Data</h3>
                <p>Upload a CSV file with role-skill mappings.</p>
                <label className="file-upload">
                  <input 
                    type="file" 
                    accept=".csv"
                    onChange={handleFileUpload}
                  />
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Choose CSV File
                </label>
                
                {modelStatus?.trained_model_exists && (
                  <button 
                    className="btn-danger"
                    onClick={handleDeleteModel}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                    Delete Trained Model
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modalMode === 'add' ? 'Add Role Mapping' : 'Edit Role Mapping'}</h2>
              <button className="modal-close" onClick={closeModal}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            
            <form onSubmit={handleFormSubmit}>
              <div className="modal-body">
                {formError && (
                  <div className="form-error">{formError}</div>
                )}
                
                <div className="form-group">
                  <label htmlFor="role">Role</label>
                  <input
                    id="role"
                    type="text"
                    placeholder="e.g., MERN Stack Developer"
                    value={formData.role}
                    onChange={(e) => setFormData(prev => ({ ...prev, role: e.target.value }))}
                  />
                </div>
                
                <div className="form-group">
                  <label htmlFor="skills">Skills (comma-separated)</label>
                  <textarea
                    id="skills"
                    placeholder="e.g., MongoDB, Express.js, React.js, Node.js"
                    rows={4}
                    value={formData.skills}
                    onChange={(e) => setFormData(prev => ({ ...prev, skills: e.target.value }))}
                  />
                </div>
              </div>
              
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : (modalMode === 'add' ? 'Add Mapping' : 'Save Changes')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default KnowledgeBase;
