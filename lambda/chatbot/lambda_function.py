# lambda/lambda_function.py
# AWS Lambda function handler for processing chat requests AND feedback
# Handles user messages, integrates with AWS Bedrock for AI responses,
# manages conversation history in DynamoDB, and retrieves information
# from knowledge bases when needed. Now also handles feedback storage using Option B.

import json
import boto3
import os
import uuid
import time
from typing import Dict, List, Tuple
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date
from boto3.dynamodb.conditions import Key, Attr
import logging

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Main Lambda handler for chat requests and feedback with full functionality"""
    
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': ''
        }
    
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Determine the path to route to appropriate handler
        path = event.get('path', '').rstrip('/')
        http_method = event.get('httpMethod', 'POST')
        
        # Route to feedback handler if it's a feedback request
        if path.endswith('/feedback') and http_method == 'POST':
            return handle_feedback_request(body)
        
        # Otherwise handle as chat request (existing logic)
        message = body.get('message', '').strip()
        session_id = body.get('sessionId', str(uuid.uuid4()))
        
        if not message or not session_id:
            return create_error_response(400, "Message/Session ID is missing")
        
        # Initialize the chatbot
        chatbot = OrcuttChatbot()
        
        # Process the chat request
        result = chatbot.process_chat_request(message, session_id)
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(result, default=decimal_default)
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")

def handle_feedback_request(body: Dict) -> Dict:
    """Handle feedback submission requests - Option B approach"""
    try:
        # Extract feedback data - safely convert to string first
        message_id = str(body.get('messageId', '')).strip()
        session_id = str(body.get('sessionId', '')).strip()
        # Support both 'feedback' and 'feedbackType' for compatibility
        feedback_type = str(body.get('feedbackType') or body.get('feedback', '')).strip().lower()
        feedback_text = str(body.get('feedbackText', '')).strip()
        
        # Validate required fields
        if not message_id or not session_id or not feedback_type:
            return create_error_response(400, "Missing required fields: messageId, sessionId, or feedbackType")
        
        # Validate feedback type
        if feedback_type not in ['up', 'down']:
            return create_error_response(400, "feedbackType must be 'up' or 'down'")
        
        # Update the existing conversation item with feedback
        chatbot = OrcuttChatbot()
        success = chatbot.update_conversation_with_feedback(session_id, message_id, feedback_type, feedback_text)
        
        if success:
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': True,
                    'message': 'Feedback saved successfully'
                })
            }
        else:
            return create_error_response(500, "Failed to save feedback")
            
    except Exception as e:
        logger.error(f"Error handling feedback request: {str(e)}")
        return create_error_response(500, f"Error saving feedback: {str(e)}")

def get_cors_headers():
    """Return standard CORS headers"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        'Content-Type': 'application/json'
    }

def decimal_default(obj):
    """Handle Decimal serialization for JSON"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def create_error_response(status_code, message):
    """Create standardized error response"""
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'error': message,
            'success': False
        })
    }

class OrcuttChatbot:
    def __init__(self):
        self.bedrock_client = None
        self.bedrock_agent_runtime = None
        self.dynamodb = None
        self.s3_client = None
        self.table = None
        self.initialize_aws_clients()
    
    def initialize_aws_clients(self):
        """Initialize AWS clients"""
        try:
            region = os.environ.get('AWS_REGION', 'us-west-2')
            
            self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)
            self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
            self.s3_client = boto3.client('s3', region_name=region)
            self.dynamodb = boto3.resource('dynamodb', region_name=region)
            self.table = self.dynamodb.Table(os.environ.get('DYNAMODB_TABLE'))
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
            raise
    
    def process_chat_request(self, message: str, session_id: str, selected_school: str) -> Dict:
        """Main method to process chat request with full functionality"""
        start_time = time.time()
        
        try:
            # Step 1: Get conversation history
            conversation_history = self.get_conversation_history(session_id)
            
            # Step 2: Classify query using Nova
            query_type = self.classify_query_with_nova(message)
            
            # Step 3: Get context from knowledge base if needed
            context = ""
            sources = []
            kb_response_school_specific = {}
            
            if query_type == 'knowledge_base':
                knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
                if knowledge_base_id:
                    kb_response = self.query_knowledge_base(message, knowledge_base_id)
                    context, sources = self.process_knowledge_base_response([kb_response])
            
            # Step 4: Generate response with conversation context
            conversation_context = self.format_conversation_context(conversation_history)
            response_text, generation_time = self.generate_response(
                message, context, query_type, conversation_context, selected_school
            )
            
            total_time = round(time.time() - start_time, 2)
            
            # Step 6: Save conversation to DynamoDB
            message_id = self.save_conversation_to_dynamodb(session_id, message, response_text, sources, total_time, query_type)
            
            return {
                'success': True,
                'response': response_text,
                'sessionId': session_id,
                'messageId': message_id,  # Include message ID for frontend feedback
                'queryType': query_type,
                'responseTime': total_time,
                'sources': sources
            }
            
        except Exception as e:
            logging.error(f"Error in process_chat_request: {str(e)}")
            error_response = "I'm sorry, I encountered an error while processing your request. Please try again."
            message_id = self.save_conversation_to_dynamodb(session_id, message, error_response, [], 0, 'error')
            return {
                'success': False,
                'response': error_response,
                'sessionId': session_id,
                'messageId': message_id,  # Include message ID even for errors
                'queryType': 'error',
                'responseTime': round(time.time() - start_time, 2),
                'sources': []
            }
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Retrieve conversation history from DynamoDB"""
        try:
            # Get conversation items
            response = self.table.query(
                KeyConditionExpression=Key('session_id').eq(session_id),
                ScanIndexForward=False,
                Limit=6
            )
            
            # Reverse to get chronological order
            items = list(reversed(response.get('Items', [])))
            
            history = []
            for item in items:
                # Add user message
                history.append({
                    'role': 'user',
                    'content': item['user_message'],
                    'timestamp': item['timestamp']
                })
                # Add assistant message
                history.append({
                    'role': 'assistant', 
                    'content': item['assistant_response'],
                    'timestamp': item['timestamp']
                })
            
            return history
            
        except Exception as e:
            logging.error(f"Error retrieving conversation history: {str(e)}")
            return []
    
    def save_conversation_to_dynamodb(self, session_id: str, user_message: str, 
                                    assistant_response: str, sources: list, 
                                    response_time: float, query_type: str) -> str:
        """Save conversation exchange to DynamoDB and return message ID"""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Get next message ID for this session
            message_id = self.get_next_message_id(session_id)
            
            conversation_item = {
                'session_id': str(session_id),
                'timestamp': str(timestamp),
                'message_id': message_id,
                'user_message': str(user_message),
                'assistant_response': str(assistant_response),
                'query_type': str(query_type),
                'response_time_seconds': Decimal(str(round(response_time, 2))),
                'created_at': str(timestamp),
                'item_type': 'conversation'
            }
            
            self.table.put_item(Item=conversation_item)
            return message_id
            
        except Exception as e:
            logging.error(f"Error saving conversation to DynamoDB: {str(e)}")
            return f"error_{int(time.time())}"  # Return error ID as fallback
    
    def update_conversation_with_feedback(self, session_id: str, message_id: str, 
                                        feedback_type: str, feedback_text: str) -> bool:
        """Update existing conversation item with feedback"""
        try:
            feedback_timestamp = datetime.now(timezone.utc).isoformat()
            
            # Find the conversation item by session_id and message_id
            response = self.table.query(
                KeyConditionExpression=Key('session_id').eq(session_id),
                FilterExpression=Attr('message_id').eq(message_id)
            )
            
            if not response['Items']:
                logger.error(f"Conversation item not found for session {session_id}, message {message_id}")
                return False
            
            # Get the first (should be only) matching item
            item = response['Items'][0]
            original_timestamp = item['timestamp']
            
            # Update the item with feedback information
            update_response = self.table.update_item(
                Key={
                    'session_id': session_id,
                    'timestamp': original_timestamp
                },
                UpdateExpression='SET feedback_type = :ft, feedback_text = :ftxt, feedback_timestamp = :fts',
                ExpressionAttributeValues={
                    ':ft': feedback_type,
                    ':ftxt': feedback_text,
                    ':fts': feedback_timestamp
                },
                ReturnValues='UPDATED_NEW'
            )
            
            logger.info(f"Feedback updated successfully for session {session_id}, message {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating conversation with feedback: {str(e)}")
            return False
    

    def get_next_message_id(self, session_id: str) -> str:
        """Get the next sequential message ID for a session"""
        try:
            # Query existing conversation messages for this session to get count
            response = self.table.query(
                KeyConditionExpression=Key('session_id').eq(session_id),
                Select='COUNT'
            )
            
            # Next message number is count + 1
            next_number = response.get('Count', 0) + 1
            return f"conv{next_number}"
            
        except Exception as e:
            logging.error(f"Error generating message ID: {str(e)}")
            # Fallback to timestamp-based ID if query fails
            return f"msg{int(time.time())}"
    
    def format_conversation_context(self, conversation_history: List[Dict]) -> str:
        """Format conversation history for Claude context"""
        if not conversation_history:
            return ""
        
        # Use last 6 messages max for context
        recent_messages = conversation_history[-6:]
        
        context = ""
        for msg in recent_messages:
            role = "Human" if msg['role'] == 'user' else "Assistant"
            content = msg['content']
            context += f"{role}: {content}\n"
        
        return context
    
    def classify_query_with_nova(self, user_input: str) -> str:
        """Classify the user query using Nova Pro/Lite"""
        # Check if classifier is enabled
        use_classifier = os.environ.get('USE_CLASSIFIER', 'false').lower() == 'true'
        if not use_classifier:
            return 'knowledge_base'
            
        try:
            # Get classifier prompt from environment and format it
            classifier_prompt_template = os.environ.get('CLASSIFIER_PROMPT', 'Classify this message as greeting, farewell, or knowledge_base: {user_input}')
            classification_prompt = classifier_prompt_template.format(user_input=user_input)

            body = json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": classification_prompt}]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 10,
                    "temperature": 0.1,
                    "topP": 0.9
                }
            })
            
            classifier_model_id = os.environ.get('CLASSIFIER_MODEL_ID', 'us.amazon.nova-lite-v1:0')
            response = self.bedrock_client.invoke_model(
                modelId=classifier_model_id,
                contentType="application/json",
                body=body
            )
            
            response_body = json.loads(response['body'].read())
            classification = response_body['output']['message']['content'][0]['text'].strip().lower()
            
            # Validate the classification result
            valid_categories = ['greeting', 'farewell', 'knowledge_base']
            if classification in valid_categories:
                return classification
            else:
                return 'knowledge_base'
                
        except Exception as e:
            logging.error(f"Error classifying query with Nova: {str(e)}")
            # Fallback to knowledge_base if Nova fails
            return 'knowledge_base'
    
    def query_knowledge_base(self, query: str, knowledge_base_id: str, metadata_filter: str = None) -> Dict:
        """Query Knowledge Base using configurable search type"""
        try:
            # Get search configuration from environment
            search_type = os.environ.get('SEARCH_TYPE', 'SEMANTIC')
            number_of_results = int(os.environ.get('NUMBER_OF_RESULTS', '10'))
            
            retrieval_config = {
                'vectorSearchConfiguration': {
                    'numberOfResults': number_of_results,
                    'overrideSearchType': search_type
                }
            }
            
            # Add filter if metadata_filter is provided
            if metadata_filter:
                retrieval_config['vectorSearchConfiguration']['filter'] = {
                    'equals': {
                        'key': 'domain',
                        'value': metadata_filter
                    }
                }
            
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={'text': query},
                retrievalConfiguration=retrieval_config
            )            
            return response
            
        except Exception as e:
            logging.error(f"Error querying knowledge base: {str(e)}")
            return {}
    
    def process_knowledge_base_response(self, kb_responses: List[Dict]) -> Tuple[str, List]:
        """Process multiple knowledge base responses and extract context and sources"""
        try:
            context = ""
            sources = []
            source_counter = 1
            
            # Process each kb_response dictionary
            for kb_response in kb_responses:
                if 'retrievalResults' in kb_response:
                    
                    for result in kb_response['retrievalResults']:
                        if 'content' in result and 'text' in result['content']:
                            chunk_text = result['content']['text']

                            # Add metadata to the context if needed
                            context += f"[Source {source_counter}]: {chunk_text}\n\n"
                            
                            # Extract source metadata
                            source_info = {
                                "filename": f"Source {source_counter}", 
                                "url": None, 
                                "s3Uri": None, 
                                "presignedUrl": None
                            }
                            
                            if 'location' in result:
                                s3_location = result['location'].get('s3Location', {})
                                if 'uri' in s3_location:
                                    s3_uri = s3_location['uri']
                                    filename = s3_uri.split('/')[-1]
                                    source_info["filename"] = filename
                                    source_info["s3Uri"] = s3_uri
                                    
                                    # Generate pre-signed URL with page number if available
                                    presigned_url = self.generate_presigned_url(s3_uri)
                                    page_number = result.get('metadata', {}).get('x-amz-bedrock-kb-document-page-number')
                                    if page_number and presigned_url:
                                        source_info["presignedUrl"] = f"{presigned_url}#page={page_number}"
                                    else:
                                        source_info["presignedUrl"] = presigned_url
                            
                            sources.append(source_info)
                            source_counter += 1
                        else:
                            break
            
            return context, sources
        
        except Exception as e:
            logging.error(f"Error processing knowledge base responses: {str(e)}")
            return "", []
    
    def generate_presigned_url(self, s3_uri: str) -> str:
        """Generate pre-signed URL for S3 object"""
        try:
            if not s3_uri.startswith('s3://'):
                return None
                
            s3_path = s3_uri[5:]
            bucket_name = s3_path.split('/')[0]
            object_key = '/'.join(s3_path.split('/')[1:])
            
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=3600
            )
            
            return presigned_url
            
        except Exception as e:
            logging.error(f"Error generating presigned URL: {str(e)}")
            return None
    
    def generate_response(self, query: str, context: str, query_type: str, conversation_context: str, selected_school: str) -> Tuple[str, float]:
        """Generate response using Claude with conversation context"""
        start_time = time.time()
        
        try:
            if query_type == 'greeting':
                response_text = os.environ.get('GREETING_RESPONSE', 'Hello! How can I help you today?')
                
            elif query_type == 'farewell':
                response_text = os.environ.get('FAREWELL_RESPONSE', 'Thank you! Have a great day!')
                
            else:  # knowledge_base
                # Get system prompt from environment variables and format it
                system_prompt_template = os.environ.get('SYSTEM_PROMPT', 'You are a helpful assistant.')
                prompt = system_prompt_template.format(
                    current_date=date.today(),
                    conversation_context=conversation_context,
                    context=context,
                    query=query,
                    selected_school=selected_school
                )

                body = {
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "anthropic_version": "bedrock-2023-05-31"
                }
                
                rag_model_id = os.environ.get('RAG_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
                response = self.bedrock_client.invoke_model(
                    modelId=rag_model_id,
                    body=json.dumps(body),
                    contentType='application/json'
                )
                
                response_body = json.loads(response['body'].read())
                response_text = response_body['content'][0]['text']
            
            response_time = round(time.time() - start_time, 2)
            return response_text, response_time
                
        except Exception as e:
            logging.error(f"Error generating response: {str(e)}")
            return "I'm sorry, I encountered an error while processing your request. Please try again or contact the school directly for assistance.", 0