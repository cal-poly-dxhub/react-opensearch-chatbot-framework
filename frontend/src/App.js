import React, { useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import logo from './assets/logo.png';
import config from './config';
import { generateDynamicStyles } from './DynamicStyles';
import './App.css';

function App() {
  useEffect(() => {
    // Apply dynamic styles based on configuration
    const dynamicStyle = generateDynamicStyles();
    document.head.appendChild(dynamicStyle);
    
    return () => {
      // Cleanup on unmount
      if (document.head.contains(dynamicStyle)) {
        document.head.removeChild(dynamicStyle);
      }
    };
  }, []);
  
  return (
    <div>
      <div style={{ 
        padding: '0.5rem',
        color: 'white',
        display: 'flex',
        justifyContent: 'center'
      }}>
        <div className="chat-header">
          <div className="header-content">
            <img src={logo} alt="Orcutt Union School District" className="header-logo" />
            <div className="header-text">
              <h1>{config.chatbot.name}</h1>
              <p style={{marginTop:-7}}>{config.chatbot.description}</p>
            </div>
          </div>
        </div>
      </div>
      <ChatInterface />
    </div>
  );
}

export default App;