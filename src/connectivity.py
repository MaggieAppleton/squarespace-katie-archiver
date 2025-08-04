"""Site connectivity and health check utilities."""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.async_api import async_playwright, Browser, Page

from .config import ArchiveConfig


class ConnectivityChecker:
    """Handles site connectivity and health checks."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.connectivity")
        
        # Set up requests session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=config.scraping.max_retries,
            backoff_factor=config.scraping.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        self.session.headers.update({
            'User-Agent': config.scraping.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def check_basic_connectivity(self) -> Dict[str, Any]:
        """Perform basic connectivity check using requests."""
        self.logger.info(f"Checking basic connectivity to {self.config.site_url}")
        
        try:
            response = self.session.get(
                self.config.site_url,
                timeout=self.config.scraping.timeout
            )
            
            result = {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'content_length': len(response.content),
                'content_type': response.headers.get('content-type', ''),
                'server': response.headers.get('server', ''),
                'last_modified': response.headers.get('last-modified', ''),
            }
            
            self.logger.info(
                f"Basic connectivity successful: {response.status_code} "
                f"({response.elapsed.total_seconds():.2f}s)"
            )
            
            return result
            
        except requests.RequestException as e:
            self.logger.error(f"Basic connectivity failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    async def check_javascript_rendering(self) -> Dict[str, Any]:
        """Check if the site requires JavaScript rendering."""
        self.logger.info("Checking JavaScript rendering requirements")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set user agent
                await page.set_extra_http_headers({
                    'User-Agent': self.config.scraping.user_agent
                })
                
                # Navigate to the site
                response = await page.goto(
                    self.config.site_url,
                    timeout=self.config.scraping.timeout * 1000
                )
                
                # Wait for potential dynamic content
                await page.wait_for_timeout(3000)  # 3 seconds
                
                # Get content
                content = await page.content()
                title = await page.title()
                
                # Check for common blog indicators
                blog_indicators = await self._find_blog_indicators(page)
                
                await browser.close()
                
                result = {
                    'success': True,
                    'status_code': response.status if response else None,
                    'title': title,
                    'content_length': len(content),
                    'has_dynamic_content': True,  # Assume true since we're testing Squarespace
                    'blog_indicators': blog_indicators
                }
                
                self.logger.info(f"JavaScript rendering check successful: {title}")
                return result
                
        except Exception as e:
            self.logger.error(f"JavaScript rendering check failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    async def _find_blog_indicators(self, page: Page) -> Dict[str, Any]:
        """Look for indicators that this is a blog site."""
        indicators = {
            'has_articles': False,
            'has_blog_posts': False,
            'has_navigation': False,
            'article_count': 0,
            'potential_post_links': []
        }
        
        try:
            # Look for article elements
            articles = await page.query_selector_all('article')
            indicators['has_articles'] = len(articles) > 0
            indicators['article_count'] = len(articles)
            
            # Look for blog-related selectors (common Squarespace patterns)
            blog_selectors = [
                '.blog-item',
                '.entry',
                '.post',
                '[data-controller="BlogItem"]',
                '.blog-item-wrapper'
            ]
            
            for selector in blog_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    indicators['has_blog_posts'] = True
                    break
            
            # Look for navigation
            nav_elements = await page.query_selector_all('nav, .navigation, .menu')
            indicators['has_navigation'] = len(nav_elements) > 0
            
            # Try to find potential blog post links
            links = await page.query_selector_all('a[href*="/blog/"], a[href*="/posts/"]')
            if links:
                for link in links[:10]:  # Limit to first 10
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    if href and text:
                        indicators['potential_post_links'].append({
                            'href': href,
                            'text': text.strip()
                        })
            
        except Exception as e:
            self.logger.warning(f"Error finding blog indicators: {e}")
        
        return indicators
    
    async def discover_blog_structure(self) -> Dict[str, Any]:
        """Discover the blog's URL structure and patterns."""
        self.logger.info("Discovering blog structure and URL patterns")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await page.set_extra_http_headers({
                    'User-Agent': self.config.scraping.user_agent
                })
                
                # First try common blog URLs
                blog_urls = [
                    self.config.site_url,
                    urljoin(self.config.site_url, '/blog/'),
                    urljoin(self.config.site_url, '/posts/'),
                    urljoin(self.config.site_url, '/articles/')
                ]
                
                structure_info = {
                    'blog_url': None,
                    'post_urls': [],
                    'pagination_info': {},
                    'url_patterns': [],
                    'total_posts_estimate': 0
                }
                
                for url in blog_urls:
                    try:
                        response = await page.goto(url, timeout=15000)
                        if response and response.status == 200:
                            # Check if this looks like a blog page
                            indicators = await self._find_blog_indicators(page)
                            if indicators['has_blog_posts'] or indicators['has_articles']:
                                structure_info['blog_url'] = url
                                self.logger.info(f"Found blog at: {url}")
                                
                                # Extract post URLs from this page
                                post_links = await self._extract_post_urls(page)
                                structure_info['post_urls'].extend(post_links)
                                
                                break
                    except Exception as e:
                        self.logger.debug(f"Failed to check {url}: {e}")
                        continue
                
                await browser.close()
                
                # Analyze URL patterns
                if structure_info['post_urls']:
                    structure_info['url_patterns'] = self._analyze_url_patterns(
                        structure_info['post_urls']
                    )
                    structure_info['total_posts_estimate'] = len(structure_info['post_urls'])
                
                self.logger.info(
                    f"Blog structure discovery complete. Found {len(structure_info['post_urls'])} posts"
                )
                
                return structure_info
                
        except Exception as e:
            self.logger.error(f"Blog structure discovery failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    async def _extract_post_urls(self, page: Page) -> List[str]:
        """Extract blog post URLs from the current page."""
        post_urls = []
        
        try:
            # Common selectors for blog post links in Squarespace
            selectors = [
                'a[href*="/blog/"]',
                '.blog-item a',
                '.entry a',
                'article a',
                '[data-controller="BlogItem"] a',
                '.blog-item-wrapper a'
            ]
            
            for selector in selectors:
                links = await page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute('href')
                    if href and self._is_blog_post_url(href):
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            href = urljoin(self.config.site_url, href)
                        
                        if href not in post_urls:
                            post_urls.append(href)
            
        except Exception as e:
            self.logger.warning(f"Error extracting post URLs: {e}")
        
        return post_urls
    
    def _is_blog_post_url(self, url: str) -> bool:
        """Check if a URL looks like a blog post."""
        # Simple heuristics for blog post URLs
        blog_patterns = [
            '/blog/',
            '/post/',
            '/posts/',
            '/article/',
            '/articles/'
        ]
        
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in blog_patterns)
    
    def _analyze_url_patterns(self, urls: List[str]) -> List[str]:
        """Analyze URL patterns to understand the blog structure."""
        patterns = set()
        
        for url in urls:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            if len(path_parts) >= 2:
                # Common pattern: /blog/post-slug
                if 'blog' in path_parts:
                    patterns.add('/blog/{slug}')
                elif 'post' in path_parts:
                    patterns.add('/post/{slug}')
                elif 'article' in path_parts:
                    patterns.add('/article/{slug}')
        
        return list(patterns)
    
    def __del__(self):
        """Clean up requests session."""
        if hasattr(self, 'session'):
            self.session.close()