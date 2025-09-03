# Chatbot Framework

A GenAI RAG ChatBot reference architecture designed to help developers quickly prototype, deploy, and launch Generative AI-powered products and services using Retrieval-Augmented Generation (RAG). By integrating advanced information retrieval with large language models, this architecture delivers accurate, contextually relevant natural language responses to user queries.

## Overview

This framework provides a complete solution for deploying production-ready chatbots with Amazon Bedrock Knowledge Base integration, featuring a modern React frontend, Lambda backend and OpenSearch Managed Cluster as the vector database. Built using AWS CDK, it leverages Amazon Bedrock for AI capabilities and includes comprehensive infrastructure automation for seamless deployment and scaling.

You can use this README file to find out how to build, deploy, use and test the code.

## Table of Contents

- [Overview](#overview)
- [Collaboration](#collaboration)
- [Disclaimers](#disclaimers)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Deployment](#initial-setup)
- [Configurations](#configuration)
- [Ingestion](#knowledge-base-sync-ingestion)
- [Support](#support)

# Collaboration

Thanks for your interest in our solution. Having specific examples of replication and usage allows us to continue to grow and scale our work. If you clone or use this repository, kindly shoot us a quick email to let us know you are interested in this work!

<wwps-cic@amazon.com>

# Disclaimers

**Customers are responsible for making their own independent assessment of the information in this document.**

**This document:**

(a) is for informational purposes only,

(b) represents current AWS product offerings and practices, which are subject to change without notice, and

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided “as is” without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers.

(d) is not to be considered a recommendation or viewpoint of AWS

**Additionally, all prototype code and associated assets should be considered:**

(a) as-is and without warranties

(b) not suitable for production environments

(d) to include shortcuts in order to support rapid prototyping such as, but not limitted to, relaxed authentication and authorization and a lack of strict adherence to security best practices

**All work produced is open source. More information can be found in the GitHub repo.**

## Authors

- Shrey Shah - <sshah84@calpoly.edu>

## Architecture

The solution consists of several key components:

1. Frontend Interface

    - React application
    - S3 + Cloudfront Hosting
    - Tailwind CSS for responsive design

2. API Layer

    - Amazon API Gateway for REST endpoints
    - AWS Lambda functions for serverless compute

3. AI Services

    - Choose from variety of LLMs for response generation
    - AWS Knowledge Bases for semantic document search
    - Query classification(optional) and intent recognition

4. Data Storage and Management

    - Amazon DynamoDB for conversation history and user sessions
    - S3 buckets for document storage and knowledge base artifacts
    - Amazon CloudWatch for application monitoring and logging

Additionally other AWS services are used for additional functionality


## Key Features

**Cost-Optimized OpenSearch Managed Cluster:**
- Uses OpenSearch managed cluster for cost optimization compared to serverless options
- Configurable instance types and sizes based on workload requirements
- Efficient vector storage and retrieval for knowledge base operations
- Semantic and hybrid search capabilities for enhanced retrieval accuracy

**Configurable React Frontend:**
- Dynamic title and branding pulled from config.yaml file
- Customizable color schemes and themes via configuration
- Modern, responsive web interface with real-time chat capabilities
- Session management with conversation history display

**DynamoDB Data Persistence:**
- All conversations automatically saved in DynamoDB table
- User feedback collection with thumbs up/down buttons
- Feedback responses and ratings stored in DynamoDB for analytics
- Session tracking and conversation analytics

**Optional Query Classification:**
- Configurable classifier model (can be enabled/disabled via config.yaml)
- Flexible classifier prompts and response templates

**Amazon Bedrock Integration:**
- Support for various embedding and text generation models
- Managed document ingestion pipeline with multiple format support

**Enterprise-Ready Architecture:**
- Infrastructure as Code using AWS CDK
- Multi-environment deployment support (dev/prod)
- Automated deployment pipeline with single-command setup
- Comprehensive security controls and encryption
- CloudFront CDN for global content delivery


## Prerequisites

- AWS CLI configured with appropriate permissions
- Node.js 18+ (for frontend)
- Python 3.13+ (for CDK and Lambda functions)
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Request model access for the required models through AWS console in Bedrock
- Docker Desktop

## Initial Setup

1. **Enable Bedrock Model Access:**
   - Navigate to the AWS Bedrock console
   - Request access to all models from both Anthropic and Amazon
   - Ensure you're working in the correct AWS region/branch for your deployment
  
2. **Download and Start Docker Desktop**
   - Verify Docker is running:
    ```bash
    docker --version
    ```

3. **Create a S3 bucket with data**
  - Create a S3 bucket in the same region
  - Add the data to S3 bucket
  - While adding metadata be sure to have the metadata file naming in this format
      - file.txt -> file.txt.metadata.json
  - While updating the config file replace the knowledge_base_bucket in s3 with this bucket name 

## Deployment Steps

1. Clone the repository
  - git clone https://github.com/cal-poly-dxhub/react-opensearch-chatbot-framework.git

2. Run the setup script
  ```bash
  cd oreact-opensearch-chatbot-framework
  ./scripts/setup.sh
  ```
  
3. Start Docker Desktop
  - Verify Docker is running:
  ```bash
  docker --version
  ```

4. Edit the .env file
```bash
AWS_REGION=us-west-2
AWS_ACCOUNT=123456789012
ENVIRONMENT=dev
```

5. Configure AWS credentials
  ```bash
  aws configure
  ```
  You'll be prompted to enter:
  
  - AWS Access Key ID
  - AWS Secret Access Key
  - Default region name
  - Default output format

6. Update Configuration
  Edit `config.yaml` to customize your chatbot:

7. Deploy the application
  ```bash
  ./scripts/deploy.sh
  ```

## Configuration

### Main Configuration File

The `config.yaml` file contains all customizable settings:

#### UI Configuration
- Chatbot name and description
- Welcome message
- Color scheme
- Branding elements

#### AI Models
- RAG model selection
- Classifier model (optional)
- System prompts
- Response templates

#### Infrastructure
- S3 bucket names
- DynamoDB table configuration
- OpenSearch cluster settings
- Lambda function parameters

#### Knowledge Base
- Embedding model
- Search configuration
- Chunking strategy
- Vector dimensions

You can update the logo.png file at /frontend/src/assets (make sure to keep the file name "logo.png")

## Knowledge Base Sync (ingestion)

- Sync Knowledge base through the AWS console by going to Amazon Bedrock then knowledge bases choose the knowledge base select the data source and click on sync button
- Sync the knowledge base through aws cli by using this command:
```bash
aws bedrock-agent start-ingestion-job \
    --knowledge-base-id your-knowledge-base-id \
    --data-source-id your-data-source-id \
    --description "Manual sync via CLI" \
    --region your-region-name
```
- Monitor Sync Job Status:
```bash
aws bedrock-agent get-ingestion-job \
    --knowledge-base-id your-knowledge-base-id \
    --data-source-id your-data-source-id \
    --ingestion-job-id your-ingestion-job-id \
    --region your-region-name
```


## Updating Changes
After making changes to the code you can deploy them by running
  ```bash
  ./scripts/deploy.sh
  ```

## Support

For any queries or issues, please contact:

- Darren Kraker - <dkraker@amazon.com>
- Shrey Shah, Jr. SDE - <sshah84@calpoly.edu>
