#!/bin/bash

# Chatbot Framework Deployment Script

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "Loading environment variables..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default environment if not specified
ENVIRONMENT=${ENVIRONMENT:-dev}

echo "Deploying Chatbot Framework to $ENVIRONMENT environment..."

# Deploy CDK stack first and save outputs to file
echo "Deploying CDK stack..."
cdk deploy --require-approval never --outputs-file /tmp/cdk-outputs.json

# Get API URL from outputs file
echo "Getting API URL..."
if [ -f /tmp/cdk-outputs.json ]; then
    API_URL=$(cat /tmp/cdk-outputs.json | grep -o '"https://[^"]*execute-api[^"]*"' | head -1 | tr -d '"')
else
    # Fallback: use CloudFormation API
    API_URL=$(aws cloudformation describe-stacks --stack-name ChatbotFrameworkStack-dev --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)
fi
echo "API URL: $API_URL"

# Build frontend with configuration and API URL
echo "Building frontend with configuration..."
REACT_APP_API_BASE_URL=$API_URL ./scripts/build-frontend.sh

# Deploy again to update frontend (REMOVE THE EXTRA cd ..)
echo "Deploying frontend..."
cdk deploy --require-approval never

echo "Deployment complete!"
echo "Check AWS Console for deployed resources"
