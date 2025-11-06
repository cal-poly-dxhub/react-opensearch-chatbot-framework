#!/usr/bin/env python3
"""
Script to invoke the web scraper Lambda function and sync knowledge base
"""

import boto3
import json
import argparse
import sys
import time
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))
from config import get_config

def invoke_webscraper(base_url, max_pages=200, max_workers=4, excluded_patterns=None):
    """
    Invoke the web scraper Lambda function
    
    Args:
        base_url (str): The base URL to scrape
        max_pages (int): Maximum number of pages to scrape
        max_workers (int): Number of concurrent workers
        excluded_patterns (list): Additional URL patterns to exclude
    """
    config = get_config()
    
    # Initialize Lambda client with extended timeout
    lambda_config = boto3.session.Config(read_timeout=900)  # 15 minutes
    lambda_client = boto3.client('lambda', config=lambda_config)
    
    # Get the Lambda function name from stack outputs
    cloudformation = boto3.client('cloudformation')
    stack_name = config.get_stack_name()
    
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        
        webscraper_arn = None
        s3_bucket = None
        
        for output in outputs:
            if output['OutputKey'] == 'WebScraperLambdaArn':
                webscraper_arn = output['OutputValue']
            elif output['OutputKey'] == 'S3BucketName':
                s3_bucket = output['OutputValue']
        
        if not webscraper_arn:
            print("Error: WebScraperLambdaArn not found in stack outputs")
            return False
            
        if not s3_bucket:
            print("Error: S3BucketName not found in stack outputs")
            return False
        
        # Prepare the payload
        payload = {
            'base_url': base_url,
            's3_bucket': s3_bucket,
            'max_pages': max_pages,
            'max_workers': max_workers
        }
        
        if excluded_patterns:
            payload['excluded_patterns'] = excluded_patterns
        
        print(f"Invoking web scraper for: {base_url}")
        print(f"S3 Bucket: {s3_bucket}")
        print(f"Max pages: {max_pages}")
        print(f"Max workers: {max_workers}")
        
        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName=webscraper_arn,
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=json.dumps(payload)
        )
        
        # Parse the response
        response_payload = json.loads(response['Payload'].read())
        
        if response['StatusCode'] == 200:
            if response_payload.get('statusCode') == 200:
                result = json.loads(response_payload['body'])
                print("\nWeb scraping completed successfully!")
                print(f"Pages crawled: {result.get('pages_crawled', 'N/A')}")
                print(f"Files downloaded: {result.get('files_downloaded', 'N/A')}")
                print(f"Base URL: {result.get('base_url', 'N/A')}")
                return True
            else:
                print(f"\nWeb scraping failed: {response_payload.get('body', 'Unknown error')}")
                return False
        else:
            print(f"\nLambda invocation failed with status code: {response['StatusCode']}")
            return False
            
    except Exception as e:
        print(f"Error invoking web scraper: {str(e)}")
        return False

def sync_knowledge_base():
    """Start knowledge base ingestion job."""
    config = get_config()
    bedrock_agent = boto3.client('bedrock-agent')
    
    # Get knowledge base and data source IDs from stack outputs
    cloudformation = boto3.client('cloudformation')
    stack_name = config.get_stack_name()
    
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        
        kb_id = None
        data_source_id = None
        
        for output in outputs:
            if output['OutputKey'] == 'KnowledgeBaseId':
                kb_id = output['OutputValue']
            elif output['OutputKey'] == 'DataSourceId':
                data_source_id = output['OutputValue'].split("|")[1]
        
        if not kb_id or not data_source_id:
            print("Error: Knowledge Base or Data Source ID not found in stack outputs")
            return False
        
        print(f"Starting knowledge base sync...")
        print(f"Knowledge Base ID: {kb_id}")
        print(f"Data Source ID: {data_source_id}")
        
        # Start ingestion job
        sync_response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id
        )
        
        job_id = sync_response['ingestionJob']['ingestionJobId']
        status = sync_response['ingestionJob']['status']
        
        print(f"\nKnowledge base sync started successfully!")
        print(f"Job ID: {job_id}")
        print(f"Status: {status}")
        
        # Monitor initial status
        time.sleep(5)
        try:
            status_response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=data_source_id,
                ingestionJobId=job_id
            )
            
            job = status_response['ingestionJob']
            current_status = job['status']
            print(f"Current Status: {current_status}")
            
            if 'statistics' in job:
                stats = job['statistics']
                if 'numberOfDocumentsScanned' in stats:
                    print(f"Documents Scanned: {stats['numberOfDocumentsScanned']}")
        except Exception:
            pass
        
        print(f"\nMonitor progress in AWS Bedrock Console")
        print(f"Ingestion typically takes 2-5 minutes")
        
        return True
        
    except Exception as e:
        print(f"Error starting knowledge base sync: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Invoke the web scraper Lambda function and sync knowledge base')
    parser.add_argument('base_url', help='Base URL to scrape')
    parser.add_argument('--max-pages', type=int, default=200, help='Maximum number of pages to scrape (default: 200)')
    parser.add_argument('--max-workers', type=int, default=4, help='Number of concurrent workers (default: 4)')
    parser.add_argument('--exclude-pattern', action='append', dest='excluded_patterns', 
                       help='Additional URL patterns to exclude (can be used multiple times)')
    parser.add_argument('--no-sync', action='store_true', help='Skip knowledge base sync after scraping')
    
    args = parser.parse_args()
    
    print("Web Scraper & Knowledge Base Sync")
    print("=" * 40)
    
    # Step 1: Run webscraper
    scraping_success = invoke_webscraper(
        base_url=args.base_url,
        max_pages=args.max_pages,
        max_workers=args.max_workers,
        excluded_patterns=args.excluded_patterns or []
    )
    
    if not scraping_success:
        print("\nWebscraping failed. Exiting.")
        sys.exit(1)
    
    # Step 2: Sync knowledge base (unless --no-sync is specified)
    if not args.no_sync:
        print("\n" + "=" * 40)
        print("STARTING KNOWLEDGE BASE SYNC")
        print("=" * 40)
        
        sync_success = sync_knowledge_base()
        
        if sync_success:
            print("\nProcess completed successfully!")
            print("Your chatbot should now have access to the scraped content.")
        else:
            print("\nWebscraping completed but knowledge base sync failed.")
            print("You can manually sync in the AWS Bedrock Console.")
            sys.exit(1)
    else:
        print("\nWebscraping completed. Skipping knowledge base sync.")
    
    sys.exit(0)

if __name__ == "__main__":
    main()