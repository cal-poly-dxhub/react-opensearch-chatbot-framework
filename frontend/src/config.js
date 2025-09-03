// Frontend configuration - populated during build
const config = {
  chatbot: {
    name: process.env.REACT_APP_CHATBOT_NAME || "My AI Assistant",
    description: process.env.REACT_APP_CHATBOT_DESCRIPTION || "Get help with information and questions",
    welcomeMessage: process.env.REACT_APP_WELCOME_MESSAGE || "Welcome! How can I help you today?"
  },
  ui: {
    colors: {
      primary: process.env.REACT_APP_UI_PRIMARY_COLOR || "#1A2F71",
      secondary: process.env.REACT_APP_UI_SECONDARY_COLOR || "#48AEB2",
      backgroundGradientStart: process.env.REACT_APP_UI_BACKGROUND_GRADIENT_START || "#1A2F71",
      backgroundGradientEnd: process.env.REACT_APP_UI_BACKGROUND_GRADIENT_END || "#48AEB2"
    }
  }
};

export default config;