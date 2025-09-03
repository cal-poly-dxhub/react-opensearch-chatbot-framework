#!/bin/bash

# Build script for frontend with configuration injection
set -e

echo "Building frontend with configuration..."

# Navigate to frontend directory
cd frontend

# Load configuration from Python config
# Load configuration from Python config and export directly
python3 -c "
import sys
import os
sys.path.append('..')
from config import get_config
config = get_config()
os.environ['REACT_APP_CHATBOT_NAME'] = config.CHATBOT_NAME
os.environ['REACT_APP_CHATBOT_DESCRIPTION'] = config.CHATBOT_DESCRIPTION
os.environ['REACT_APP_WELCOME_MESSAGE'] = config.WELCOME_MESSAGE.replace('\n', '\\n')
os.environ['REACT_APP_UI_PRIMARY_COLOR'] = config.UI_PRIMARY_COLOR
os.environ['REACT_APP_UI_SECONDARY_COLOR'] = config.UI_SECONDARY_COLOR
os.environ['REACT_APP_UI_BACKGROUND_GRADIENT_START'] = config.UI_BACKGROUND_GRADIENT_START
os.environ['REACT_APP_UI_BACKGROUND_GRADIENT_END'] = config.UI_BACKGROUND_GRADIENT_END
" && \
export REACT_APP_CHATBOT_NAME="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().CHATBOT_NAME)')" && \
export REACT_APP_CHATBOT_DESCRIPTION="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().CHATBOT_DESCRIPTION)')" && \
export REACT_APP_WELCOME_MESSAGE="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().WELCOME_MESSAGE.replace("\n", "\\n"))')" && \
export REACT_APP_UI_PRIMARY_COLOR="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().UI_PRIMARY_COLOR)')" && \
export REACT_APP_UI_SECONDARY_COLOR="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().UI_SECONDARY_COLOR)')" && \
export REACT_APP_UI_BACKGROUND_GRADIENT_START="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().UI_BACKGROUND_GRADIENT_START)')" && \
export REACT_APP_UI_BACKGROUND_GRADIENT_END="$(python3 -c 'import sys; sys.path.append(".."); from config import get_config; print(get_config().UI_BACKGROUND_GRADIENT_END)')"

# Export API URL if provided
if [ ! -z "$REACT_APP_API_BASE_URL" ]; then
    export REACT_APP_API_BASE_URL
    echo "  API URL: $REACT_APP_API_BASE_URL"
fi

echo "Building with configuration:"
echo "  Chatbot Name: $REACT_APP_CHATBOT_NAME"
echo "  Description: $REACT_APP_CHATBOT_DESCRIPTION"
echo "  Welcome Message: $REACT_APP_WELCOME_MESSAGE"
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