#!/usr/bin/env python3
"""
Simple, targeted scraper for historical blog posts (2005-2014).
Uses basic web scraping to extract content from the older .html format.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

async def scrape_historical_posts():
    """Scrape pre-2015 blog posts using simple HTTP requests."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("historical_scraper")
    
    logger.info("Starting simple historical blog post scraping...")
    
    # Get pre-2015 URLs from the archive state
    archive_state_path = Path("enhanced_output/archive_state.json")
    if not archive_state_path.exists():
        logger.error("Archive state file not found. Run the enhanced discovery first.")
        return
    
    with open(archive_state_path) as f:
        archive_state = json.load(f)
    
    all_urls = archive_state.get("all_urls", [])
    
    # Filter for only pre-2015 blog posts
    pre_2015_urls = []
    for url in all_urls:
        # Check if it's a historical blog post (2005-2014)
        if any(f"/{year}/" in url for year in range(2005, 2015)):
            # Only include actual blog posts, not tag/category pages
            if ("/libedge/" in url and 
                not "/tag/" in url and 
                not "/category/" in url and
                not "/p/" in url):
                pre_2015_urls.append(url)
    
    logger.info(f"Found {len(pre_2015_urls)} pre-2015 blog post URLs to scrape")
    
    # Show breakdown by year
    year_breakdown = {}
    for url in pre_2015_urls:
        for year in range(2005, 2015):
            if f"/{year}/" in url:
                year_breakdown[year] = year_breakdown.get(year, 0) + 1
                break
    
    logger.info("Pre-2015 posts by year:")
    for year in sorted(year_breakdown.keys()):
        logger.info(f"  {year}: {year_breakdown[year]} posts")
    
    # Set up requests session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    # Create output directory
    output_dir = Path("pre_2015_output")
    output_dir.mkdir(exist_ok=True)
    
    extracted_posts = []
    failed_urls = []
    
    # Process each URL
    for i, url in enumerate(pre_2015_urls, 1):
        logger.info(f"Processing {i}/{len(pre_2015_urls)}: {url}")
        
        try:
            # Make HTTP request
            response = session.get(url, timeout=30)
            
            if response.status_code == 200:
                # Parse HTML content
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract post data
                post_data = extract_post_from_soup(soup, url)
                
                if post_data and post_data.get('content'):
                    extracted_posts.append(post_data)
                    logger.info(f"✅ Successfully extracted: {post_data.get('title', 'No title')}")
                else:
                    failed_urls.append(url)
                    logger.warning(f"❌ No content found: {url}")
            else:
                failed_urls.append(url)
                logger.warning(f"❌ HTTP {response.status_code}: {url}")
                
        except Exception as e:
            failed_urls.append(url)
            logger.error(f"❌ Error scraping {url}: {e}")
        
        # Small delay to be respectful
        await asyncio.sleep(0.5)
    
    logger.info(f"Scraping complete: {len(extracted_posts)} successful, {len(failed_urls)} failed")
    
    if extracted_posts:
        # Save results
        save_results(extracted_posts, failed_urls, year_breakdown, output_dir, logger)
    else:
        logger.error("No posts were successfully extracted!")

def extract_post_from_soup(soup: BeautifulSoup, url: str) -> dict:
    """Extract post data from BeautifulSoup object."""
    
    post_data = {
        'url': url,
        'scraped_at': datetime.now().isoformat(),
        'id': generate_post_id(url),
        'slug': extract_slug_from_url(url)
    }
    
    # Try multiple selectors for title
    title_selectors = [
        'h1.entry-title',
        'h1',
        '.entry-title',
        '.post-title', 
        'title',
        'h2.entry-title'
    ]
    
    title = None
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title and len(title) > 3:  # Reasonable title length
                break
    
    if title:
        post_data['title'] = title
    else:
        # Fallback: extract from URL
        post_data['title'] = extract_title_from_url(url)
    
    # Try multiple selectors for content
    content_selectors = [
        '.entry-content',
        '.post-content',
        '.content',
        'article',
        '.entry',
        '.post-body',
        '.main-content'
    ]
    
    content = None
    for selector in content_selectors:
        content_elem = soup.select_one(selector)
        if content_elem:
            # Get text content, preserving some structure
            content = content_elem.get_text(separator='\n\n', strip=True)
            if content and len(content) > 100:  # Reasonable content length
                break
    
    if content:
        post_data['content'] = content
        post_data['content_length'] = len(content)
        post_data['word_count'] = len(content.split())
    
    # Try to extract date from URL pattern
    date_match = re.search(r'/(\d{4})/(\d{1,2})/', url)
    if date_match:
        year, month = date_match.groups()
        try:
            # Create a rough date (first of the month)
            post_data['published_date'] = f"{year}-{month:0>2}-01"
            post_data['year'] = int(year)
            post_data['month'] = int(month)
        except:
            pass
    
    # Try to extract author (likely Katie Day for this blog)
    post_data['author'] = 'Katie Day'
    
    # Add some metadata
    post_data['extraction_method'] = 'simple_html_scraping'
    
    return post_data

def generate_post_id(url: str) -> str:
    """Generate a unique ID for the post based on URL."""
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split('/') if part]
    if len(path_parts) >= 2:
        return '_'.join(path_parts[-2:])  # year_month_title pattern
    return path_parts[-1] if path_parts else 'unknown'

def extract_slug_from_url(url: str) -> str:
    """Extract slug from URL."""
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split('/') if part]
    # Return the last part (likely the title slug)
    return path_parts[-1] if path_parts else ''

def extract_title_from_url(url: str) -> str:
    """Extract a readable title from URL as fallback."""
    slug = extract_slug_from_url(url)
    if slug.endswith('.html'):
        slug = slug[:-5]  # Remove .html
    # Convert hyphens to spaces and capitalize
    title = slug.replace('-', ' ').replace('_', ' ')
    return title.title()

def save_results(extracted_posts: list, failed_urls: list, year_breakdown: dict, output_dir: Path, logger):
    """Save extraction results."""
    
    # Save JSON
    json_output = output_dir / "pre_2015_posts.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump({
            "extraction_date": datetime.now().isoformat(),
            "extraction_method": "simple_html_scraping",
            "total_posts": len(extracted_posts),
            "posts": extracted_posts,
            "failed_urls": failed_urls,
            "year_breakdown": year_breakdown
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(extracted_posts)} posts to {json_output}")
    
    # Create markdown files
    markdown_dir = output_dir / "markdown"
    markdown_dir.mkdir(exist_ok=True)
    
    for post in extracted_posts:
        # Create safe filename
        title = post.get('title', 'Untitled')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title[:50]  # Limit length
        
        date_str = ""
        if post.get('published_date'):
            date_str = post['published_date'][:10]  # YYYY-MM-DD
        
        filename = f"{date_str}_{safe_title}.md" if date_str else f"{safe_title}.md"
        filename = filename.replace(" ", "_")
        
        # Create markdown content
        markdown_content = f"""# {post.get('title', 'Untitled')}

**URL:** {post.get('url', '')}  
**Published:** {post.get('published_date', 'Unknown')}  
**Author:** {post.get('author', 'Katie Day')}  
**Word Count:** {post.get('word_count', 'Unknown')}

---

{post.get('content', 'No content available')}
"""
        
        markdown_file = markdown_dir / filename
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
    
    logger.info(f"Created {len(extracted_posts)} markdown files in {markdown_dir}")
    
    # Summary report
    logger.info("=" * 60)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total URLs processed: {len(extracted_posts) + len(failed_urls)}")
    logger.info(f"Successfully extracted: {len(extracted_posts)}")
    logger.info(f"Failed extractions: {len(failed_urls)}")
    
    if extracted_posts:
        success_rate = len(extracted_posts)/(len(extracted_posts) + len(failed_urls))*100
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        # Word count stats
        word_counts = [post.get('word_count', 0) for post in extracted_posts if post.get('word_count')]
        if word_counts:
            logger.info(f"Average words per post: {sum(word_counts)/len(word_counts):.0f}")
    
    if failed_urls:
        logger.info("Sample failed URLs:")
        for url in failed_urls[:3]:
            logger.info(f"  - {url}")
        if len(failed_urls) > 3:
            logger.info(f"  ... and {len(failed_urls) - 3} more")

if __name__ == "__main__":
    asyncio.run(scrape_historical_posts())