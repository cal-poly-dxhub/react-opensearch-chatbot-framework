#!/usr/bin/env python3
"""
Script to scrape all websites listed in config.yaml
"""

import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))
from config import get_config
from scripts.invoke_webscraper import invoke_webscraper, sync_knowledge_base

def main():
    """Scrape all websites from config and sync knowledge base."""
    config = get_config()
    
    websites = config.WEBSCRAPER_WEBSITES
    
    if not websites:
        print("No websites configured in config.yaml")
        print("Add websites under lambda.webscraper.websites_to_scrape")
        sys.exit(1)
    
    print("Starting batch webscraper...")
    print(f"Found {len(websites)} websites to scrape:")
    for i, url in enumerate(websites, 1):
        print(f"  {i}. {url}")
    print()
    
    successful_scrapes = 0
    
    # Scrape each website
    for i, base_url in enumerate(websites, 1):
        print(f"[{i}/{len(websites)}] Scraping: {base_url}")
        
        success = invoke_webscraper(
            base_url=base_url,
            max_pages=config.WEBSCRAPER_MAX_PAGES,
            max_workers=config.WEBSCRAPER_MAX_WORKERS,
            excluded_patterns=[]
        )
        
        if success:
            successful_scrapes += 1
            print(f"Successfully scraped: {base_url}")
        else:
            print(f"Failed to scrape: {base_url}")
        
        print("-" * 50)
    
    print(f"\nScraping Summary:")
    print(f"Total websites: {len(websites)}")
    print(f"Successful: {successful_scrapes}")
    print(f"Failed: {len(websites) - successful_scrapes}")
    
    if successful_scrapes > 0:
        print("\n" + "=" * 50)
        print("STARTING KNOWLEDGE BASE SYNC")
        print("=" * 50)
        
        sync_success = sync_knowledge_base()
        
        if sync_success:
            print("\nAll done! Your chatbot now has access to the scraped content.")
        else:
            print("\nScraping completed but knowledge base sync failed.")
            print("You can manually sync in the AWS Bedrock Console.")
    else:
        print("\nNo websites were successfully scraped.")
        sys.exit(1)

if __name__ == "__main__":
    main()