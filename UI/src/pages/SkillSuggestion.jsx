import { useState, useEffect, useCallback, useMemo } from 'react';
import { useDebounce } from '../hooks/useDebounce';
import { suggestSkills, getHealth } from '../services/api';
import SkillCard from '../components/SkillCard';
import LoadingSpinner from '../components/LoadingSpinner';
import './SkillSuggestion.css';

function SkillSuggestion() {
  // Input state
  const [role, setRole] = useState('');
  const [limit, setLimit] = useState(10);
  const [useMapping, setUseMapping] = useState(true);
  
  // API state
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  
  // Debounce the role input (300ms delay)
  const debouncedRole = useDebounce(role, 300);
  
  // Fetch health status on mount
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const status = await getHealth();
        setHealthStatus(status);
      } catch (err) {
        console.error('Failed to fetch health:', err);
        setHealthStatus({ status: 'unhealthy', error: err.message });
      }
    };
    fetchHealth();
  }, []);
  
  // Fetch suggestions when debounced role changes
  useEffect(() => {
    const fetchSuggestions = async () => {
      // Don't fetch if role is too short
      if (!debouncedRole || debouncedRole.trim().length < 2) {
        setResults(null);
        return;
      }
      
      setLoading(true);
      setError(null);
      
      try {
        const data = await suggestSkills(debouncedRole, limit, useMapping);
        setResults(data);
      } catch (err) {
        setError(err.message);
        setResults(null);
      } finally {
        setLoading(false);
      }
    };
    
    fetchSuggestions();
  }, [debouncedRole, limit, useMapping]);
  
  // Handle input change
  const handleRoleChange = useCallback((e) => {
    setRole(e.target.value);
  }, []);
  
  // Handle limit change
  const handleLimitChange = useCallback((e) => {
    setLimit(Number(e.target.value));
  }, []);
  
  // Handle mapping toggle
  const handleMappingToggle = useCallback(() => {
    setUseMapping((prev) => !prev);
  }, []);
  
  // Clear search
  const handleClear = useCallback(() => {
    setRole('');
    setResults(null);
    setError(null);
  }, []);
  
  // Memoized skill count
  const skillCount = useMemo(() => {
    return results?.skills?.length || 0;
  }, [results]);
  
  // Determine if currently typing (role differs from debounced)
  const isTyping = role !== debouncedRole;
  
  return (
    <div className="suggestion-page">
      {/* Hero Section */}
      <div className="hero-section">
        <h1 className="hero-title">Find the Perfect Skills</h1>
        <p className="hero-subtitle">
          Enter a job role to discover relevant skills using AI-powered hybrid search
        </p>
        
        {/* Status Indicator */}
        <div className="status-indicator">
          <span className={`status-dot ${healthStatus?.status === 'healthy' ? 'healthy' : 'unhealthy'}`} />
          <span className="status-text">
            {healthStatus?.status === 'healthy' 
              ? `${healthStatus?.skills_loaded?.toLocaleString()} skills indexed`
              : 'Service unavailable'}
          </span>
        </div>
      </div>
      
      {/* Search Section */}
      <div className="search-section">
        <div className="search-container">
          <div className="search-input-wrapper">
            <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Enter job role (e.g., MERN Stack Developer, Data Scientist)"
              value={role}
              onChange={handleRoleChange}
              autoFocus
            />
            {role && (
              <button className="clear-button" onClick={handleClear} title="Clear">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
            {(loading || isTyping) && (
              <div className="search-loading">
                <LoadingSpinner size="small" />
              </div>
            )}
          </div>
          
          {/* Search Options */}
          <div className="search-options">
            <div className="option-group">
              <label htmlFor="limit" className="option-label">Results:</label>
              <select 
                id="limit" 
                className="option-select"
                value={limit}
                onChange={handleLimitChange}
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
                <option value={30}>30</option>
              </select>
            </div>
            
            <label className="option-toggle">
              <input
                type="checkbox"
                checked={useMapping}
                onChange={handleMappingToggle}
              />
              <span className="toggle-slider" />
              <span className="toggle-label">Use Direct Mappings</span>
            </label>
          </div>
        </div>
      </div>
      
      {/* Results Section */}
      <div className="results-section">
        {/* Error State */}
        {error && (
          <div className="error-message">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{error}</span>
          </div>
        )}
        
        {/* Empty State */}
        {!loading && !error && !results && role.length < 2 && (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p>Start typing a job role to see skill suggestions</p>
          </div>
        )}
        
        {/* No Results */}
        {!loading && !error && results && skillCount === 0 && (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>No skills found for "{results.normalized_role}"</p>
            <span className="empty-hint">Try a different role or disable direct mappings</span>
          </div>
        )}
        
        {/* Results */}
        {results && skillCount > 0 && (
          <>
            <div className="results-header">
              <div className="results-info">
                <span className="results-count">{skillCount} skills</span>
                <span className="results-role">for "{results.normalized_role}"</span>
              </div>
              <div className="search-method-badge">
                {results.search_method === 'mapped' && (
                  <span className="method-badge mapped">Direct Match</span>
                )}
                {results.search_method === 'semantic' && (
                  <span className="method-badge semantic">Semantic Search</span>
                )}
                {results.search_method === 'hybrid' && (
                  <span className="method-badge hybrid">Hybrid</span>
                )}
              </div>
            </div>
            
            <div className="skills-grid">
              {results.skills.map((skill, index) => (
                <SkillCard 
                  key={`${skill.skill_id}-${index}`} 
                  skill={skill} 
                  index={index}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default SkillSuggestion;
