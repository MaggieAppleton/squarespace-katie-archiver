"""Advanced site exploration to understand blog structure."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
import re
from playwright.async_api import async_playwright, Browser, Page

from .config import ArchiveConfig


class SiteExplorer:
    """Advanced site exploration for discovering blog content."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.explorer")
        self.discovered_urls: Set[str] = set()
        self.blog_posts: List[Dict[str, Any]] = []
    
    async def comprehensive_discovery(self) -> Dict[str, Any]:
        """Perform comprehensive blog discovery."""
        self.logger.info("Starting comprehensive blog discovery...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                # Step 1: Explore main page and common blog paths
                main_page_info = await self._explore_main_page(browser)
                
                # Step 2: Look for sitemap or RSS feeds
                sitemap_info = await self._discover_sitemap(browser)
                
                # Step 3: Try common Squarespace blog patterns
                squarespace_patterns = await self._try_squarespace_patterns(browser)
                
                # Step 4: Explore navigation menus
                navigation_info = await self._explore_navigation(browser)
                
                # Step 5: Look for archive pages
                archive_info = await self._explore_archives(browser)
                
                # Compile results
                discovery_results = {
                    'main_page': main_page_info,
                    'sitemap': sitemap_info,
                    'squarespace_patterns': squarespace_patterns,
                    'navigation': navigation_info,
                    'archives': archive_info,
                    'total_posts_found': len(self.blog_posts),
                    'discovered_posts': self.blog_posts[:10],  # First 10 for preview
                    'all_discovered_urls': list(self.discovered_urls)[:20]  # First 20 URLs
                }
                
                self.logger.info(f"Discovery complete. Found {len(self.blog_posts)} potential blog posts")
                return discovery_results
                
            finally:
                await browser.close()
    
    async def _explore_main_page(self, browser: Browser) -> Dict[str, Any]:
        """Explore the main page for blog content and navigation."""
        self.logger.info("Exploring main page...")
        
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
        
        try:
            await page.goto(self.config.site_url, timeout=30000)
            await page.wait_for_timeout(3000)  # Let dynamic content load
            
            # Get page info
            title = await page.title()
            url = page.url
            
            # Look for all links
            links = await self._extract_all_links(page)
            blog_links = [link for link in links if self._looks_like_blog_post(link['href'])]
            
            # Look for specific Squarespace elements
            squarespace_elements = await self._find_squarespace_elements(page)
            
            # Check for blog-related text content
            page_text = await page.inner_text('body')
            has_blog_keywords = any(keyword in page_text.lower() for keyword in 
                                   ['blog', 'posts', 'articles', 'recent', 'latest'])
            
            self.discovered_urls.update([link['href'] for link in links])
            
            result = {
                'title': title,
                'url': url,
                'total_links': len(links),
                'blog_links': blog_links,
                'has_blog_keywords': has_blog_keywords,
                'squarespace_elements': squarespace_elements
            }
            
            self.logger.info(f"Main page: {title} - Found {len(blog_links)} potential blog links")
            return result
            
        except Exception as e:
            self.logger.error(f"Error exploring main page: {e}")
            return {'error': str(e)}
            
        finally:
            await page.close()
    
    async def _discover_sitemap(self, browser: Browser) -> Dict[str, Any]:
        """Try to find and parse sitemap.xml or robots.txt."""
        self.logger.info("Looking for sitemap...")
        
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
        
        sitemap_urls = [
            urljoin(self.config.site_url, '/sitemap.xml'),
            urljoin(self.config.site_url, '/sitemap_index.xml'),
            urljoin(self.config.site_url, '/robots.txt')
        ]
        
        found_sitemaps = []
        blog_urls_from_sitemap = []
        
        try:
            for sitemap_url in sitemap_urls:
                try:
                    response = await page.goto(sitemap_url, timeout=15000)
                    if response and response.status == 200:
                        content = await page.content()
                        
                        if 'sitemap' in sitemap_url:
                            # Parse XML sitemap
                            blog_urls = self._parse_sitemap_for_blog_urls(content)
                            blog_urls_from_sitemap.extend(blog_urls)
                            found_sitemaps.append({
                                'url': sitemap_url,
                                'blog_urls_found': len(blog_urls)
                            })
                        else:
                            # Parse robots.txt for sitemap references
                            sitemap_refs = self._parse_robots_for_sitemaps(content)
                            if sitemap_refs:
                                found_sitemaps.append({
                                    'url': sitemap_url,
                                    'sitemap_references': sitemap_refs
                                })
                        
                        self.logger.info(f"Found sitemap: {sitemap_url}")
                        
                except Exception as e:
                    self.logger.debug(f"Failed to access {sitemap_url}: {e}")
                    continue
            
            self.discovered_urls.update(blog_urls_from_sitemap)
            
            return {
                'found_sitemaps': found_sitemaps,
                'blog_urls_from_sitemap': blog_urls_from_sitemap[:10],  # First 10
                'total_blog_urls': len(blog_urls_from_sitemap)
            }
            
        except Exception as e:
            self.logger.error(f"Error in sitemap discovery: {e}")
            return {'error': str(e)}
            
        finally:
            await page.close()
    
    async def _try_squarespace_patterns(self, browser: Browser) -> Dict[str, Any]:
        """Try common Squarespace URL patterns."""
        self.logger.info("Trying Squarespace-specific patterns...")
        
        # Common Squarespace blog URL patterns
        patterns_to_try = [
            '/blog',
            '/blog/',
            '/posts',
            '/posts/',
            '/articles',
            '/articles/',
            '/news',
            '/news/',
            '/writing',
            '/writing/',
            '/journal',
            '/journal/'
        ]
        
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
        
        successful_patterns = []
        
        try:
            for pattern in patterns_to_try:
                test_url = urljoin(self.config.site_url, pattern)
                
                try:
                    response = await page.goto(test_url, timeout=15000)
                    if response and response.status == 200:
                        # Check if this looks like a blog page
                        await page.wait_for_timeout(2000)
                        
                        # Look for blog post elements
                        blog_elements = await self._find_squarespace_elements(page)
                        links = await self._extract_all_links(page)
                        blog_links = [link for link in links if self._looks_like_blog_post(link['href'])]
                        
                        if blog_elements['blog_items'] > 0 or len(blog_links) > 0:
                            successful_patterns.append({
                                'pattern': pattern,
                                'url': test_url,
                                'blog_elements': blog_elements,
                                'blog_links_found': len(blog_links)
                            })
                            
                            # Add discovered URLs
                            self.discovered_urls.update([link['href'] for link in links])
                            
                            self.logger.info(f"Found blog content at: {test_url}")
                        
                except Exception as e:
                    self.logger.debug(f"Pattern {pattern} failed: {e}")
                    continue
            
            return {
                'patterns_tested': len(patterns_to_try),
                'successful_patterns': successful_patterns
            }
            
        finally:
            await page.close()
    
    async def _explore_navigation(self, browser: Browser) -> Dict[str, Any]:
        """Explore site navigation for blog sections."""
        self.logger.info("Exploring site navigation...")
        
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
        
        try:
            await page.goto(self.config.site_url, timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Find navigation elements
            nav_selectors = [
                'nav', '.nav', '.navigation', '.menu', '.header-nav',
                '[data-nc-group="top"]', '.header-menu', '.main-nav'
            ]
            
            navigation_links = []
            
            for selector in nav_selectors:
                try:
                    nav_elements = await page.query_selector_all(selector)
                    for nav in nav_elements:
                        links = await nav.query_selector_all('a')
                        for link in links:
                            href = await link.get_attribute('href')
                            text = await link.inner_text()
                            
                            if href and text:
                                # Check if this might be a blog section
                                text_lower = text.lower().strip()
                                if any(keyword in text_lower for keyword in 
                                      ['blog', 'posts', 'articles', 'news', 'writing', 'journal']):
                                    navigation_links.append({
                                        'href': href if href.startswith('http') else urljoin(self.config.site_url, href),
                                        'text': text.strip(),
                                        'selector': selector
                                    })
                except Exception as e:
                    self.logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            # Remove duplicates
            unique_nav_links = []
            seen_urls = set()
            for link in navigation_links:
                if link['href'] not in seen_urls:
                    unique_nav_links.append(link)
                    seen_urls.add(link['href'])
            
            self.discovered_urls.update(seen_urls)
            
            return {
                'navigation_links': unique_nav_links,
                'total_nav_links': len(unique_nav_links)
            }
            
        except Exception as e:
            self.logger.error(f"Error exploring navigation: {e}")
            return {'error': str(e)}
            
        finally:
            await page.close()
    
    async def _explore_archives(self, browser: Browser) -> Dict[str, Any]:
        """Look for archive pages or date-based organization."""
        self.logger.info("Looking for archive pages...")
        
        # Try common archive patterns
        archive_patterns = [
            '/archive',
            '/archive/',
            '/?view=archive',
            '/blog/archive',
            '/posts/archive'
        ]
        
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
        
        found_archives = []
        
        try:
            for pattern in archive_patterns:
                test_url = urljoin(self.config.site_url, pattern)
                
                try:
                    response = await page.goto(test_url, timeout=15000)
                    if response and response.status == 200:
                        await page.wait_for_timeout(2000)
                        
                        # Look for date-organized content or post lists
                        links = await self._extract_all_links(page)
                        blog_links = [link for link in links if self._looks_like_blog_post(link['href'])]
                        
                        if len(blog_links) > 0:
                            found_archives.append({
                                'url': test_url,
                                'posts_found': len(blog_links)
                            })
                            
                            self.discovered_urls.update([link['href'] for link in links])
                            
                except Exception as e:
                    self.logger.debug(f"Archive pattern {pattern} failed: {e}")
                    continue
            
            return {
                'archive_pages': found_archives,
                'total_archives': len(found_archives)
            }
            
        finally:
            await page.close()
    
    async def _extract_all_links(self, page: Page) -> List[Dict[str, str]]:
        """Extract all links from a page."""
        try:
            links = await page.query_selector_all('a[href]')
            result = []
            
            for link in links:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                
                if href:
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = urljoin(self.config.site_url, href)
                    elif not href.startswith('http'):
                        href = urljoin(page.url, href)
                    
                    result.append({
                        'href': href,
                        'text': text.strip() if text else ''
                    })
            
            return result
            
        except Exception as e:
            self.logger.warning(f"Error extracting links: {e}")
            return []
    
    async def _find_squarespace_elements(self, page: Page) -> Dict[str, Any]:
        """Look for Squarespace-specific blog elements."""
        elements = {
            'blog_items': 0,
            'articles': 0,
            'post_containers': 0,
            'squarespace_indicators': []
        }
        
        # Squarespace blog selectors
        squarespace_selectors = [
            '.blog-item',
            '.blog-item-wrapper',
            '[data-controller="BlogItem"]',
            '.blog-basic-grid--text',
            '.blog-list-item',
            '.entry-wrap',
            '.journal-entry'
        ]
        
        try:
            for selector in squarespace_selectors:
                elements_found = await page.query_selector_all(selector)
                count = len(elements_found)
                
                if count > 0:
                    elements['blog_items'] += count
                    elements['squarespace_indicators'].append({
                        'selector': selector,
                        'count': count
                    })
            
            # Also check for articles
            articles = await page.query_selector_all('article')
            elements['articles'] = len(articles)
            
        except Exception as e:
            self.logger.warning(f"Error finding Squarespace elements: {e}")
        
        return elements
    
    def _looks_like_blog_post(self, url: str) -> bool:
        """Heuristic to determine if a URL looks like a blog post."""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Positive indicators
        blog_indicators = [
            '/blog/', '/post/', '/posts/', '/article/', '/articles/',
            '/news/', '/writing/', '/journal/', '/entry/'
        ]
        
        # Negative indicators (admin, static pages, etc.)
        negative_indicators = [
            '/admin', '/login', '/contact', '/about', '/home',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
            'mailto:', 'tel:', '#', 'javascript:'
        ]
        
        # Check negative indicators first
        if any(neg in url_lower for neg in negative_indicators):
            return False
        
        # Check positive indicators
        if any(pos in url_lower for pos in blog_indicators):
            return True
        
        # Check if URL has a slug-like pattern (common in blog posts)
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        # Look for date patterns or slug patterns
        if len(path_parts) >= 1:
            last_part = path_parts[-1]
            # Check for slug-like patterns (words separated by hyphens)
            if re.match(r'^[a-z0-9-]+$', last_part) and len(last_part) > 3:
                return True
        
        return False
    
    def _parse_sitemap_for_blog_urls(self, sitemap_content: str) -> List[str]:
        """Parse sitemap XML for potential blog URLs."""
        blog_urls = []
        
        try:
            # Simple regex-based parsing (could be improved with proper XML parsing)
            url_pattern = r'<loc>(.*?)</loc>'
            urls = re.findall(url_pattern, sitemap_content)
            
            for url in urls:
                if self._looks_like_blog_post(url):
                    blog_urls.append(url)
            
        except Exception as e:
            self.logger.warning(f"Error parsing sitemap: {e}")
        
        return blog_urls
    
    def _parse_robots_for_sitemaps(self, robots_content: str) -> List[str]:
        """Parse robots.txt for sitemap references."""
        sitemaps = []
        
        try:
            lines = robots_content.split('\n')
            for line in lines:
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    sitemaps.append(sitemap_url)
        
        except Exception as e:
            self.logger.warning(f"Error parsing robots.txt: {e}")
        
        return sitemaps