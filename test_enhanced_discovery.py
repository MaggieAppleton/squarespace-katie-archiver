#!/usr/bin/env python3
"""Test script for enhanced URL discovery to find historical posts."""

import asyncio
import sys
import logging
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import ConfigManager
from src.url_discovery import URLDiscovery

async def test_enhanced_discovery():
    """Test the enhanced URL discovery functionality."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("test_discovery")
    logger.info("Starting enhanced URL discovery test...")
    
    # Load configuration
    config = ConfigManager.load_config()
    logger.info(f"Target site: {config.site_url}")
    
    # Create URL discovery instance
    discovery = URLDiscovery(config)
    
    # Test enhanced discovery
    results = await discovery.discover_all_blog_urls()
    
    # Report results
    logger.info("=" * 60)
    logger.info("ENHANCED DISCOVERY RESULTS")
    logger.info("=" * 60)
    
    for method, count in results['discovery_methods'].items():
        logger.info(f"{method.capitalize()}: {count} URLs")
    
    logger.info(f"Total unique URLs found: {results['total_unique_urls']}")
    
    # Show breakdown by year
    all_urls = results['all_urls']
    year_breakdown = {}
    
    for url in all_urls:
        # Try to extract year from URL
        for year in range(2005, 2025):
            if f'/{year}/' in url:
                year_breakdown[year] = year_breakdown.get(year, 0) + 1
                break
    
    if year_breakdown:
        logger.info("Year breakdown:")
        for year in sorted(year_breakdown.keys()):
            logger.info(f"  {year}: {year_breakdown[year]} posts")
    
    # Show first few URLs for verification
    logger.info("Sample URLs found:")
    for i, url in enumerate(all_urls[:10]):
        logger.info(f"  {i+1}: {url}")
    
    if len(all_urls) > 10:
        logger.info(f"  ... and {len(all_urls) - 10} more")
    
    # Check for historical content
    historical_urls = [url for url in all_urls if any(f'/{year}/' in url for year in range(2005, 2015))]
    if historical_urls:
        logger.info(f"✅ Found {len(historical_urls)} historical posts (2005-2014)")
        logger.info("Historical URLs:")
        for url in historical_urls:
            logger.info(f"  {url}")
    else:
        logger.warning("❌ No historical posts found (2005-2014)")
    
    logger.info("Enhanced discovery test complete!")
    
    return results

if __name__ == "__main__":
    # Run the test
    results = asyncio.run(test_enhanced_discovery())