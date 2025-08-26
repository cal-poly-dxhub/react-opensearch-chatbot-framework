import config from './config';

// Generate dynamic CSS based on configuration
export const generateDynamicStyles = () => {
  const { colors } = config.ui;
  
  const style = document.createElement('style');
  style.textContent = `
    :root {
      --primary-color: ${colors.primary};
      --secondary-color: ${colors.secondary};
      --gradient-start: ${colors.backgroundGradientStart};
      --gradient-end: ${colors.backgroundGradientEnd};
    }
    
    .chat-container {
      background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%) !important;
    }
    
    .header-content h1 {
      color: var(--primary-color) !important;
    }
    
    .header-content p {
      color: var(--secondary-color) !important;
    }
    
    .user-message {
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;
    }
    
    .message-input:focus {
      border-color: var(--primary-color) !important;
      box-shadow: 0 0 0 3px rgba(${hexToRgb(colors.primary)}, 0.1) !important;
    }
    
    .send-button {
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;
    }
    
    .send-button:hover:not(:disabled) {
      box-shadow: 0 8px 24px rgba(${hexToRgb(colors.primary)}, 0.4) !important;
    }
    
    .new-session-button {
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;
    }
    
    .new-session-button:hover {
      box-shadow: 0 6px 20px rgba(${hexToRgb(colors.primary)}, 0.3) !important;
    }
    
    .pdf-download-btn {
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;
    }
    
    .pdf-download-btn:hover:not(:disabled) {
      box-shadow: 0 6px 20px rgba(${hexToRgb(colors.primary)}, 0.3) !important;
    }
    
    .feedback-submit-btn {
      background: var(--primary-color) !important;
    }
    
    .feedback-submit-btn:hover {
      background: var(--secondary-color) !important;
    }
    
    .input-status {
      color: var(--primary-color) !important;
    }
    
    .welcome-message h3 {
      color: var(--primary-color) !important;
    }
    
    .message-link {
      color: var(--primary-color) !important;
    }
    
    .message-link:hover {
      color: var(--secondary-color) !important;
    }
    
    .typing-indicator span {
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;
    }
    
    .school-dropdown:focus {
      border-color: var(--primary-color) !important;
      box-shadow: 0 0 0 2px rgba(${hexToRgb(colors.primary)}, 0.2) !important;
    }
    
    .school-dropdown optgroup {
      color: var(--primary-color) !important;
    }
  `;
  
  return style;
};

// Helper function to convert hex to RGB
const hexToRgb = (hex) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result 
    ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
    : '26, 47, 113'; // fallback to default primary color
};

export default generateDynamicStyles;