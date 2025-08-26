#!/bin/bash

# Build script for frontend with configuration injection
set -e

echo "Building frontend with configuration..."

# Navigate to frontend directory
cd frontend

# Load configuration from Python config
CONFIG_VALUES=$(python3 -c "
import sys
sys.path.append('..')
from config import get_config
config = get_config()
print(f'REACT_APP_CHATBOT_NAME=\"{config.CHATBOT_NAME}\"')
print(f'REACT_APP_CHATBOT_DESCRIPTION=\"{config.CHATBOT_DESCRIPTION}\"')
print(f'REACT_APP_UI_PRIMARY_COLOR=\"{config.UI_PRIMARY_COLOR}\"')
print(f'REACT_APP_UI_SECONDARY_COLOR=\"{config.UI_SECONDARY_COLOR}\"')
print(f'REACT_APP_UI_BACKGROUND_GRADIENT_START=\"{config.UI_BACKGROUND_GRADIENT_START}\"')
print(f'REACT_APP_UI_BACKGROUND_GRADIENT_END=\"{config.UI_BACKGROUND_GRADIENT_END}\"')
")

# Export environment variables
export $CONFIG_VALUES

# Export API URL if provided
if [ ! -z "$REACT_APP_API_BASE_URL" ]; then
    export REACT_APP_API_BASE_URL
    echo "  API URL: $REACT_APP_API_BASE_URL"
fi

echo "Building with configuration:"
echo "  Chatbot Name: $REACT_APP_CHATBOT_NAME"
echo "  Description: $REACT_APP_CHATBOT_DESCRIPTION"
echo "  Primary Color: $REACT_APP_UI_PRIMARY_COLOR"
echo "  Secondary Color: $REACT_APP_UI_SECONDARY_COLOR"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Build the React app
echo "Building React app..."
npm run build

echo "Frontend build completed successfully!"