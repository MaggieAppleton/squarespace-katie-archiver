#!/usr/bin/env python3
"""
Focused extractor for pre-2015 blog posts.
Only extracts historical content (2005-2014) from the discovered URLs.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import ConfigManager
from src.content_extractor import ContentExtractor

async def extract_pre_2015_posts():
    """Extract only pre-2015 blog posts efficiently."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("pre_2015_extractor")
    logger.info("Starting focused pre-2015 blog post extraction...")
    
    # Load configuration
    config = ConfigManager.load_config()
    
    # Get pre-2015 URLs from the archive state
    archive_state_path = Path("enhanced_output/archive_state.json")
    if not archive_state_path.exists():
        logger.error("Archive state file not found. Run the enhanced discovery first.")
        return
    
    with open(archive_state_path) as f:
        archive_state = json.load(f)
    
    all_urls = archive_state.get("all_urls", [])
    
    # Filter for only pre-2015 blog posts (exclude tags, categories, microblog)
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
    
    logger.info(f"Found {len(pre_2015_urls)} pre-2015 blog post URLs to extract")
    
    if not pre_2015_urls:
        logger.warning("No pre-2015 URLs found!")
        return
    
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
    
    # Create output directory
    output_dir = Path("pre_2015_output")
    output_dir.mkdir(exist_ok=True)
    
    # Create extractor with modified settings for .html URLs
    extractor = ContentExtractor(config)
    
    # Extract content from pre-2015 URLs
    logger.info("Starting content extraction...")
    
    extracted_posts = []
    failed_urls = []
    
    for i, url in enumerate(pre_2015_urls, 1):
        logger.info(f"Processing {i}/{len(pre_2015_urls)}: {url}")
        
        try:
            # Extract content for this single URL
            posts = await extractor.extract_posts_from_urls([url])
            
            if posts:
                extracted_posts.extend(posts)
                logger.info(f"✅ Successfully extracted: {url}")
            else:
                failed_urls.append(url)
                logger.warning(f"❌ Failed to extract: {url}")
                
        except Exception as e:
            failed_urls.append(url)
            logger.error(f"❌ Error extracting {url}: {e}")
        
        # Small delay to be respectful
        await asyncio.sleep(1)
    
    logger.info(f"Extraction complete: {len(extracted_posts)} successful, {len(failed_urls)} failed")
    
    if extracted_posts:
        # Save extracted posts as JSON
        json_output = output_dir / "pre_2015_posts.json"
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump({
                "extraction_date": datetime.now().isoformat(),
                "total_posts": len(extracted_posts),
                "posts": extracted_posts,
                "failed_urls": failed_urls,
                "year_breakdown": year_breakdown
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(extracted_posts)} posts to {json_output}")
        
        # Create markdown files for each post
        markdown_dir = output_dir / "markdown"
        markdown_dir.mkdir(exist_ok=True)
        
        for post in extracted_posts:
            # Create safe filename
            title = post.get('title', 'Untitled')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]  # Limit length
            
            date_str = ""
            if post.get('published_date'):
                try:
                    date_obj = datetime.fromisoformat(post['published_date'].replace('Z', '+00:00'))
                    date_str = date_obj.strftime("%Y-%m-%d")
                except:
                    pass
            
            filename = f"{date_str}_{safe_title}.md" if date_str else f"{safe_title}.md"
            filename = filename.replace(" ", "_")
            
            # Create markdown content
            markdown_content = f"""# {post.get('title', 'Untitled')}

**URL:** {post.get('url', '')}  
**Published:** {post.get('published_date', 'Unknown')}  
**Author:** {post.get('author', 'Katie Day')}

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
        logger.info(f"Total URLs processed: {len(pre_2015_urls)}")
        logger.info(f"Successfully extracted: {len(extracted_posts)}")
        logger.info(f"Failed extractions: {len(failed_urls)}")
        logger.info(f"Success rate: {len(extracted_posts)/len(pre_2015_urls)*100:.1f}%")
        
        if failed_urls:
            logger.info("Failed URLs:")
            for url in failed_urls[:5]:  # Show first 5
                logger.info(f"  - {url}")
            if len(failed_urls) > 5:
                logger.info(f"  ... and {len(failed_urls) - 5} more")
    
    else:
        logger.error("No posts were successfully extracted!")

if __name__ == "__main__":
    # Run the extraction
    asyncio.run(extract_pre_2015_posts())