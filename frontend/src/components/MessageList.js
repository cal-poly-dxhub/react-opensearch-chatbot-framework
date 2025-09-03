// src/components/MessageList.js
import React, { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import config from '../config';

const MessageList = ({ messages, isLoading, sessionId }) => {
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Format welcome message with line breaks
  const formatWelcomeMessage = (message) => {
    // Handle both actual newlines and escaped \n sequences
    const normalizedMessage = message.replace(/\\n/g, '\n');
    return normalizedMessage.split(/\r?\n/).map((line, index) => {
      if (line.trim().startsWith('- ')) {
        return <li key={index}>{line.trim().substring(2)}</li>;
      } else if (line.trim()) {
        return <p key={index}>{line.trim()}</p>;
      }
      return null;
    }).filter(Boolean);
  };

  return (
    <div className="message-list">
      {messages.length === 0 && (
        <div className="welcome-message">
          <h3>Welcome to {config.chatbot.name}!</h3>
          {formatWelcomeMessage(config.chatbot.welcomeMessage.replace(/^Welcome to.*?\n/, ''))}
        </div>
      )}
      
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} sessionId={sessionId} />
      ))}
      
      {isLoading && (
        <div className="loading-message">
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span>Assistant is typing...</span>
        </div>
      )}
      
      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;