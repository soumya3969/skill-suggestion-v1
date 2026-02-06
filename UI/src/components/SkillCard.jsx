import './SkillCard.css';

function SkillCard({ skill, index }) {
  const { skill_name, confidence, source } = skill;
  
  // Calculate confidence percentage and color
  const confidencePercent = Math.round(confidence * 100);
  const confidenceColor = getConfidenceColor(confidence);
  
  return (
    <div 
      className="skill-card"
      style={{ 
        animationDelay: `${index * 50}ms`,
        '--confidence-color': confidenceColor 
      }}
    >
      <div className="skill-card-content">
        <div className="skill-header">
          <h3 className="skill-name">{skill_name}</h3>
          <span className={`source-badge ${source}`}>
            {source === 'mapped' ? 'Direct Match' : 'Semantic'}
          </span>
        </div>
        
        <div className="confidence-section">
          <div className="confidence-bar-container">
            <div 
              className="confidence-bar" 
              style={{ 
                width: `${confidencePercent}%`,
                backgroundColor: confidenceColor
              }}
            />
          </div>
          <span className="confidence-value" style={{ color: confidenceColor }}>
            {confidencePercent}%
          </span>
        </div>
      </div>
    </div>
  );
}

function getConfidenceColor(confidence) {
  if (confidence >= 0.9) return '#10b981'; // Green
  if (confidence >= 0.7) return '#3b82f6'; // Blue
  if (confidence >= 0.5) return '#f59e0b'; // Yellow
  return '#6b7280'; // Gray
}

export default SkillCard;
