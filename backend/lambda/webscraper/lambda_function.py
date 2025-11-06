#!/usr/bin/env python3
"""
Generic Web Scraper Lambda Function
Scrapes website content and saves to S3 for knowledge base ingestion
"""

import json
import boto3
import requests
from bs4 import BeautifulSoup
import re
import hashlib
from urllib.parse import urljoin, urlparse, parse_qs
from collections import deque
from datetime import datetime
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET
from pypdf import PdfReader
import io

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class WebScraper:
    def __init__(self, base_url, s3_bucket, max_workers=4, max_pages=200, excluded_patterns=None, excluded_urls=None):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.s3_bucket = s3_bucket
        self.max_workers = max_workers
        self.max_pages = max_pages
        self.logger = logger
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
        
        # Track visited URLs and downloaded files
        self.visited_urls = set()
        self.downloaded_files = set()
        
        # Thread-safe locks
        self.visited_lock = threading.Lock()
        self.downloaded_lock = threading.Lock()
        
        # File extensions to download
        self.downloadable_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.csv'
        }
        
        # File extensions to exclude
        self.excluded_extensions = {
            '.css', '.js', '.ico', '.png', '.jpg', '.jpeg', '.gif',
            '.woff', '.woff2', '.ttf', '.eot', '.map', '.json'
        }

        # URL patterns to exclude
        self.excluded_url_patterns = [
            r'pageID=smartSiteFeed',
            r'pageID=.*Feed',
            r'pageID=rss',
            r'pageID=json',
            r'pageID=xml',
            r'pageID=api',
            r'feed=.*%',
            r'articleID=\d+',
            r'ajax=.*',
            r'callback=.*',
            r'\.json\?',
            r'\.xml\?',
            r'export=.*',
            r'print=.*',
        ]
        
        # Add custom excluded patterns if provided
        if excluded_patterns:
            self.excluded_url_patterns.extend(excluded_patterns)
        
        # Specific URLs to exclude
        self.excluded_urls = set(excluded_urls or [])
    
    def create_session(self):
        """Create a new session for each thread."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        return session
    
    def is_feed_or_dynamic_url(self, url):
        """Check if URL is a feed or dynamic content endpoint that should be excluded."""
        for pattern in self.excluded_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.debug(f"Excluding feed/dynamic URL: {url} (matched pattern: {pattern})")
                return True
        
        # Additional check for complex query parameters
        parsed = urlparse(url)
        if parsed.query:
            query_params = parse_qs(parsed.query)
            
            for param, values in query_params.items():
                for value in values:
                    if (len(value) > 100 or
                        '%22' in value or
                        '%7B' in value or
                        '%5B' in value or
                        value.count('%') > 10):
                        logger.debug(f"Excluding complex parameter URL: {url}")
                        return True
        
        return False
    
    def is_valid_url(self, url):
        """Check if URL is valid and belongs to the target domain."""
        try:
            # Check if URL is in excluded URLs list
            if url in self.excluded_urls:
                logger.debug(f"Excluding specific URL: {url}")
                return False
                
            if self.is_feed_or_dynamic_url(url):
                return False
            
            parsed = urlparse(url)
            
            # Domain checking
            is_same_domain = (
                parsed.netloc == self.domain or 
                parsed.netloc == f"www.{self.domain}" or
                parsed.netloc == self.domain.replace('www.', '') or
                parsed.netloc.endswith(f".{self.domain.replace('www.', '')}")
            )
            
            is_valid_scheme = parsed.scheme in ['http', 'https']
            
            # Exclude problematic URLs
            is_excluded = any(exclude in url.lower() for exclude in [
                'mailto:', 'tel:', 'javascript:', '#', 'void(0)', 'data:'
            ])
            
            # Allow relative URLs and same-domain URLs
            is_relative = not parsed.netloc or is_same_domain
            
            return (is_valid_scheme or not parsed.scheme) and is_relative and not is_excluded
            
        except Exception as e:
            logger.debug(f"URL validation error for {url}: {str(e)}")
            return False
    
    def sanitize_filename(self, filename):
        """Sanitize filename for safe storage."""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        return filename[:200]  # Limit length
    
    def get_url_hash(self, url):
        """Generate a short hash for the URL to use in filenames."""
        return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def get_domain_prefix(self, url):
        """Extract short domain prefix."""
        domain = urlparse(url).netloc
        if domain.startswith('www.'):
            return 'main'
        elif '.' in domain:
            return domain.split('.')[0]
        return 'main'
    
    def create_bedrock_metadata(self, original_url, filename, title="", content_type="text/plain", 
                               file_size=0, source_webpage_url=None):
        """Create AWS Bedrock-compatible metadata."""
        
        # Determine document type
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if file_ext == 'txt':
            doc_type = "webpage"
            doc_category = "web_content"
        elif file_ext == 'pdf':
            doc_type = "document"
            doc_category = "pdf_document"
        elif file_ext in ['doc', 'docx']:
            doc_type = "document"
            doc_category = "word_document"
        elif file_ext in ['xls', 'xlsx']:
            doc_type = "spreadsheet"
            doc_category = "excel_document"
        elif file_ext in ['ppt', 'pptx']:
            doc_type = "presentation"
            doc_category = "powerpoint_document"
        else:
            doc_type = "file"
            doc_category = "other_document"
        
        # Determine page type
        filename_lower = filename.lower()
        if 'index' in filename_lower or filename_lower.startswith('home'):
            page_type = "homepage"
        elif 'about' in filename_lower:
            page_type = "about"
        elif 'contact' in filename_lower:
            page_type = "contact"
        else:
            page_type = "content"
        
        # Create AWS Bedrock compatible metadata
        metadata = {
            "metadataAttributes": {
                "source": source_webpage_url or original_url,
                "file_url": original_url,
                "title": title or filename,
                "document_type": doc_type,
                "document_category": doc_category,
                "page_type": page_type,
                "file_extension": f".{file_ext}",
                "last_modified": datetime.now().strftime('%Y-%m-%d'),
                "content_type": content_type,
                "domain": urlparse(source_webpage_url or original_url).netloc,
            }
        }
        
        # Add file size if available
        if file_size > 0:
            metadata["metadataAttributes"]["file_size"] = int(file_size)
        
        return metadata
    
    def upload_to_s3(self, content, s3_key, content_type='application/octet-stream'):
        """Upload content directly to S3 bucket root."""
        try:
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=content,
                ContentType=content_type
            )
            logger.info(f"Uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload to S3: {str(e)}")
            return False
    
    def s3_file_exists(self, s3_key):
        """Check if file already exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=s3_key)
            return True
        except:
            return False
    
    def download_from_s3(self, s3_key):
        """Download file content from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            return response['Body'].read()
        except:
            return None
    
    def get_s3_filename(self, url, filename, source_url=None):
        """Generate S3 filename with domain prefix."""
        domain_prefix = self.get_domain_prefix(url)
        safe_filename = self.sanitize_filename(filename)
        return f"{domain_prefix}_{safe_filename}"
    
    def extract_text_content(self, soup):
        """Extract readable text content from BeautifulSoup object."""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def file_already_exists(self, url, filename):
        """Check if file already exists to avoid re-downloading."""
        s3_filename = self.get_s3_filename(url, filename)
        metadata_filename = f"{s3_filename}.metadata.json"
        
        if self.s3_file_exists(s3_filename) and self.s3_file_exists(metadata_filename):
            try:
                # Check if metadata contains the same file URL
                metadata_content = self.download_from_s3(metadata_filename)
                if metadata_content:
                    metadata = json.loads(metadata_content.decode('utf-8'))
                    meta_attrs = metadata.get('metadataAttributes', {})
                    if (meta_attrs.get('file_url') == url or 
                        meta_attrs.get('source') == url):
                        logger.info(f"File already exists, skipping: {filename}")
                        return True
            except Exception:
                pass
        return False
    
    def download_file(self, url, source_url):
        """Download a file and save to S3 with metadata."""
        try:
            session = self.create_session()
            logger.info(f"Downloading file: {url}")
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            # Get filename from URL or Content-Disposition header
            filename = None
            if 'Content-Disposition' in response.headers:
                cd = response.headers['Content-Disposition']
                filename_match = re.search(r'filename="?([^"]+)"?', cd)
                if filename_match:
                    filename = filename_match.group(1)
            
            if not filename:
                filename = urlparse(url).path.split('/')[-1]
                if not filename or '.' not in filename:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'pdf' in content_type:
                        ext = '.pdf'
                    else:
                        ext = '.bin'
                    filename = f"file_{self.get_url_hash(url)}{ext}"
            
            filename = self.sanitize_filename(filename)
            
            # Check if file already exists
            if self.file_already_exists(url, filename):
                with self.downloaded_lock:
                    self.downloaded_files.add(url)
                return True
            
            # Ensure unique filename
            counter = 1
            original_filename = filename
            s3_filename = self.get_s3_filename(url, filename)
            while self.s3_file_exists(s3_filename):
                name, ext = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, '')
                filename = f"{name}_{counter}.{ext}" if ext else f"{name}_{counter}"
                s3_filename = self.get_s3_filename(url, filename)
                counter += 1
            
            # Upload file to S3
            content_type = response.headers.get('content-type', 'application/octet-stream')
            if self.upload_to_s3(response.content, s3_filename, content_type):
                
                # Create and upload metadata
                metadata = self.create_bedrock_metadata(
                    original_url=url,
                    filename=filename,
                    title=filename,
                    content_type=content_type,
                    file_size=len(response.content),
                    source_webpage_url=source_url
                )
                
                metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
                metadata_filename = f"{s3_filename}.metadata.json"
                self.upload_to_s3(metadata_json, metadata_filename, 'application/json')
                
                with self.downloaded_lock:
                    self.downloaded_files.add(url)
                
                logger.info(f"Successfully uploaded file: {filename}")
                return True
            
        except Exception as e:
            logger.error(f"Error downloading file {url}: {str(e)}")
        
        return False
    
    def webpage_already_exists(self, url):
        """Check if webpage already exists to avoid re-processing."""
        # Create potential filename
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        domain_prefix = self.get_domain_prefix(url)
        
        if path_parts:
            filename = f"{domain_prefix}_{'_'.join(path_parts)}"
        else:
            filename = f"{domain_prefix}_index"
        
        if parsed_url.query:
            filename += f"_query_{self.get_url_hash(parsed_url.query)}"
        
        filename = self.sanitize_filename(filename) + '.txt'
        metadata_filename = f"{filename}.metadata.json"
        
        if self.s3_file_exists(filename) and self.s3_file_exists(metadata_filename):
            try:
                metadata_content = self.download_from_s3(metadata_filename)
                if metadata_content:
                    metadata = json.loads(metadata_content.decode('utf-8'))
                    if metadata.get('metadataAttributes', {}).get('source') == url:
                        logger.info(f"Webpage already exists, skipping: {filename}")
                        return True
            except Exception:
                pass
        return False
    
    def save_webpage(self, url, soup, response_content):
        """Save webpage content as text file to S3 with metadata."""
        try:
            # Check if webpage already exists
            if self.webpage_already_exists(url):
                return True
            
            # Create filename based on URL
            parsed_url = urlparse(url)
            path_parts = [part for part in parsed_url.path.split('/') if part]
            
            domain_prefix = self.get_domain_prefix(url)
            
            if path_parts:
                filename = f"{domain_prefix}_{'_'.join(path_parts)}"
            else:
                filename = f"{domain_prefix}_index"
            
            if parsed_url.query:
                filename += f"_query_{self.get_url_hash(parsed_url.query)}"
            
            filename = self.sanitize_filename(filename) + '.txt'
            
            # Ensure unique filename
            counter = 1
            original_filename = filename
            while self.s3_file_exists(filename):
                name = original_filename.replace('.txt', '')
                filename = f"{name}_{counter}.txt"
                counter += 1
            
            # Extract and prepare text content
            text_content = self.extract_text_content(soup)
            title = soup.title.string if soup.title else filename
            
            # Create full text content
            full_content = f"URL: {url}\nTitle: {title}\n{'=' * 50}\n\n{text_content}"
            
            # Upload webpage to S3
            if self.upload_to_s3(full_content, filename, 'text/plain'):
                
                # Create and upload metadata
                metadata = self.create_bedrock_metadata(
                    original_url=url,
                    filename=filename,
                    title=title,
                    content_type="text/plain",
                    file_size=len(full_content.encode('utf-8')),
                    source_webpage_url=url
                )
                
                metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
                metadata_filename = f"{filename}.metadata.json"
                self.upload_to_s3(metadata_json, metadata_filename, 'application/json')
                
                logger.info(f"Saved webpage to S3: {filename}")
                return True
            
        except Exception as e:
            logger.error(f"Error saving webpage {url}: {str(e)}")
        
        return False
    
    def find_links_and_files(self, soup, base_url):
        """Extract all links and downloadable files from the page."""
        links = set()
        files = set()
        
        # Find all links in ALL tags
        for tag in soup.find_all(['a', 'link', 'area']):
            href = tag.get('href')
            if href:
                full_url = urljoin(base_url, href)
                
                # Check if it's a downloadable file
                parsed = urlparse(full_url)
                path_lower = parsed.path.lower()
                
                is_downloadable = any(path_lower.endswith(ext) for ext in self.downloadable_extensions)
                is_excluded = any(path_lower.endswith(ext) for ext in self.excluded_extensions)
                
                is_file = is_downloadable and not is_excluded
                
                if is_file:
                    files.add(full_url)
                elif self.is_valid_url(full_url):
                    # Don't crawl excluded file types as webpages
                    is_excluded_type = any(path_lower.endswith(ext) for ext in self.excluded_extensions)
                    if not is_excluded_type:
                        links.add(full_url)
        
        # Also check for files in other tags
        for tag in soup.find_all(['embed', 'object', 'iframe']):
            src = tag.get('src') or tag.get('data')
            if src:
                full_url = urljoin(base_url, src)
                parsed = urlparse(full_url)
                path_lower = parsed.path.lower()
                
                is_downloadable = any(path_lower.endswith(ext) for ext in self.downloadable_extensions)
                is_excluded = any(path_lower.endswith(ext) for ext in self.excluded_extensions)
                
                if is_downloadable and not is_excluded:
                    files.add(full_url)
        
        # Look for data attributes that might contain URLs
        for tag in soup.find_all(attrs={'data-href': True}):
            href = tag.get('data-href')
            if href:
                full_url = urljoin(base_url, href)
                if self.is_valid_url(full_url):
                    links.add(full_url)
        
        logger.debug(f"Found {len(links)} links and {len(files)} files on {base_url}")
        
        return links, files
    
    def fetch_sitemap_urls(self):
        """Fetch URLs from sitemap.xml if it exists."""
        sitemap_urls = set()
        
        sitemap_locations = ['/sitemap.xml', '/sitemap_index.xml', '/sitemap.xml.gz']
        
        for sitemap_path in sitemap_locations:
            sitemap_url = urljoin(self.base_url, sitemap_path)
            
            try:
                session = self.create_session()
                logger.info(f"Checking for sitemap: {sitemap_url}")
                response = session.get(sitemap_url, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"Found sitemap: {sitemap_url}")
                    
                    try:
                        root = ET.fromstring(response.content)
                        
                        # Standard sitemap
                        for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                            loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                            if loc_elem is not None and loc_elem.text:
                                url = loc_elem.text.strip()
                                if self.is_valid_url(url):
                                    sitemap_urls.add(url)
                        
                        # Sitemap index
                        for sitemap_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                            loc_elem = sitemap_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                            if loc_elem is not None and loc_elem.text:
                                sub_sitemap_url = loc_elem.text.strip()
                                sub_urls = self.fetch_sub_sitemap(sub_sitemap_url)
                                sitemap_urls.update(sub_urls)
                        
                        logger.info(f"Found {len(sitemap_urls)} URLs in sitemap: {sitemap_url}")
                        break
                        
                    except ET.ParseError as e:
                        logger.warning(f"Could not parse sitemap XML {sitemap_url}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Sitemap not found or error accessing {sitemap_url}: {str(e)}")
                continue
        
        if sitemap_urls:
            logger.info(f"Total URLs found in sitemaps: {len(sitemap_urls)}")
        else:
            logger.info("No sitemaps found or no valid URLs in sitemaps")
        
        return sitemap_urls
    
    def fetch_sub_sitemap(self, sitemap_url):
        """Fetch URLs from a sub-sitemap."""
        urls = set()
        try:
            session = self.create_session()
            response = session.get(sitemap_url, timeout=30)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                    loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                    if loc_elem is not None and loc_elem.text:
                        url = loc_elem.text.strip()
                        if self.is_valid_url(url):
                            urls.add(url)
                            
        except Exception as e:
            logger.warning(f"Error fetching sub-sitemap {sitemap_url}: {str(e)}")
        
        return urls
    
    def process_url(self, url):
        """Process a single URL - to be used with threading."""
        try:
            session = self.create_session()
            logger.info(f"Crawling: {url}")
            response = session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Save webpage to S3
            self.save_webpage(url, soup, response.content)
            
            # Find links and files
            links, files = self.find_links_and_files(soup, url)
            
            return links, files, url
            
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            return set(), set(), url
    
    def download_files_threaded(self, file_urls_with_source):
        """Download files using threading."""
        if not file_urls_with_source:
            return
            
        logger.info(f"Starting threaded download of {len(file_urls_with_source)} files...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit download tasks
            future_to_url = {
                executor.submit(self.download_file, file_url, source_url): (file_url, source_url)
                for file_url, source_url in file_urls_with_source
                if file_url not in self.downloaded_files
            }
            
            # Process completed downloads
            for future in as_completed(future_to_url):
                file_url, source_url = future_to_url[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Download failed for {file_url}: {str(e)}")
    
    def crawl_website(self):
        """Main crawling function with threading support."""
        logger.info(f"Starting to crawl: {self.base_url}")
        
        # Queue for URLs to visit - start with base URL and sitemap URLs
        url_queue = deque([self.base_url])
        
        # Add sitemap URLs to the queue
        sitemap_urls = self.fetch_sitemap_urls()
        for url in sitemap_urls:
            if url not in self.visited_urls:
                url_queue.append(url)
        
        logger.info(f"Starting crawl with {len(url_queue)} URLs (including {len(sitemap_urls)} from sitemap)")
        
        # Track crawling statistics
        pages_processed = 0
        total_links_found = 0
        
        while url_queue and pages_processed < self.max_pages:
            # Process URLs in batches
            current_batch = []
            batch_size = min(self.max_workers, len(url_queue))
            
            for _ in range(batch_size):
                if url_queue:
                    url = url_queue.popleft()
                    with self.visited_lock:
                        if url not in self.visited_urls:
                            current_batch.append(url)
                            self.visited_urls.add(url)
            
            if not current_batch:
                break
            
            # Process batch of URLs with threading
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_url = {
                    executor.submit(self.process_url, url): url 
                    for url in current_batch
                }
                
                batch_files = []
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        links, files, processed_url = future.result()
                        pages_processed += 1
                        total_links_found += len(links)
                        
                        # Add files to download list
                        for file_url in files:
                            batch_files.append((file_url, processed_url))
                        
                        # Add new links to queue
                        new_links_added = 0
                        for link in links:
                            with self.visited_lock:
                                if link not in self.visited_urls:
                                    url_queue.append(link)
                                    new_links_added += 1
                        
                        if new_links_added > 0:
                            logger.debug(f"Added {new_links_added} new links from {processed_url}")
                                    
                    except Exception as e:
                        logger.error(f"Error processing results for {url}: {str(e)}")
                
                # Download files from this batch
                if batch_files:
                    self.download_files_threaded(batch_files)
                
                # Log progress periodically
                if pages_processed % 10 == 0:
                    logger.info(f"Progress: {pages_processed} pages processed, {len(url_queue)} in queue, {total_links_found} total links found")
        
        logger.info(f"Crawling completed. Visited {len(self.visited_urls)} pages, downloaded {len(self.downloaded_files)} files.")

def lambda_handler(event, context):
    """Lambda function handler."""
    try:
        # Get parameters from event
        base_url = event.get('base_url')
        s3_bucket = event.get('s3_bucket')
        max_workers = event.get('max_workers', 4)
        max_pages = event.get('max_pages', 200)
        excluded_patterns = event.get('excluded_patterns', [])
        excluded_urls = event.get('excluded_urls', [])
        
        if not base_url or not s3_bucket:
            return {
                'statusCode': 400,
                'body': json.dumps('Missing required parameters: base_url and s3_bucket')
            }
        
        # Create scraper and start crawling
        scraper = WebScraper(base_url, s3_bucket, max_workers, max_pages, excluded_patterns, excluded_urls)
        scraper.crawl_website()
        
        # Return results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scraping completed successfully',
                'base_url': base_url,
                'pages_crawled': len(scraper.visited_urls),
                'files_downloaded': len(scraper.downloaded_files),
                's3_bucket': s3_bucket
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda function error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }