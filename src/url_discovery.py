"""Comprehensive URL discovery system for blog posts."""

import asyncio
import logging
import re
from typing import List, Dict, Any, Set, Optional
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from playwright.async_api import async_playwright, Browser

from .config import ArchiveConfig
from .site_explorer import SiteExplorer


class URLDiscovery:
    """Comprehensive URL discovery for blog posts."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.url_discovery")
        self.discovered_urls: Set[str] = set()
        
        # Set up requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.scraping.user_agent
        })
    
    async def discover_all_blog_urls(self) -> Dict[str, Any]:
        """Discover all blog post URLs using multiple methods."""
        self.logger.info("Starting comprehensive URL discovery...")
        
        discovery_results = {
            'sitemap_urls': [],
            'navigation_urls': [],
            'archive_urls': [],
            'pagination_urls': [],
            'manual_crawl_urls': [],
            'total_unique_urls': 0,
            'all_urls': [],
            'discovery_methods': {}
        }
        
        # Method 1: Sitemap discovery (most reliable)
        sitemap_urls = await self._discover_from_sitemap()
        discovery_results['sitemap_urls'] = sitemap_urls
        discovery_results['discovery_methods']['sitemap'] = len(sitemap_urls)
        self.discovered_urls.update(sitemap_urls)
        
        # Method 2: Navigation and known pages
        nav_urls = await self._discover_from_navigation()
        discovery_results['navigation_urls'] = nav_urls
        discovery_results['discovery_methods']['navigation'] = len(nav_urls)
        self.discovered_urls.update(nav_urls)
        
        # Method 3: Archive pages
        archive_urls = await self._discover_from_archives()
        discovery_results['archive_urls'] = archive_urls
        discovery_results['discovery_methods']['archives'] = len(archive_urls)
        self.discovered_urls.update(archive_urls)
        
        # Method 4: Pagination discovery
        pagination_urls = await self._discover_from_pagination()
        discovery_results['pagination_urls'] = pagination_urls
        discovery_results['discovery_methods']['pagination'] = len(pagination_urls)
        self.discovered_urls.update(pagination_urls)
        
        # Method 5: Manual crawling of blog sections
        crawl_urls = await self._discover_from_crawling()
        discovery_results['manual_crawl_urls'] = crawl_urls
        discovery_results['discovery_methods']['crawling'] = len(crawl_urls)
        self.discovered_urls.update(crawl_urls)
        
        # Filter and deduplicate
        final_urls = self._filter_and_validate_urls(list(self.discovered_urls))
        
        discovery_results['all_urls'] = final_urls
        discovery_results['total_unique_urls'] = len(final_urls)
        
        self.logger.info(f"URL discovery complete. Found {len(final_urls)} unique blog post URLs")
        
        # Show method breakdown
        for method, count in discovery_results['discovery_methods'].items():
            self.logger.info(f"  {method.capitalize()}: {count} URLs")
        
        return discovery_results
    
    async def _discover_from_sitemap(self) -> List[str]:
        """Discover URLs from sitemap.xml."""
        self.logger.info("Discovering URLs from sitemap...")
        
        urls = []
        sitemap_urls = [
            urljoin(self.config.site_url, '/sitemap.xml'),
            urljoin(self.config.site_url, '/sitemap_index.xml')
        ]
        
        for sitemap_url in sitemap_urls:
            try:
                response = self.session.get(sitemap_url, timeout=30)
                if response.status_code == 200:
                    sitemap_urls_found = self._parse_sitemap_xml(response.content)
                    urls.extend(sitemap_urls_found)
                    self.logger.info(f"Found {len(sitemap_urls_found)} URLs in {sitemap_url}")
                    
                    # If this is a sitemap index, process sub-sitemaps
                    if 'sitemap_index' in sitemap_url or 'sitemap' in response.text:
                        sub_sitemaps = self._extract_sub_sitemaps(response.content)
                        for sub_sitemap in sub_sitemaps:
                            try:
                                sub_response = self.session.get(sub_sitemap, timeout=30)
                                if sub_response.status_code == 200:
                                    sub_urls = self._parse_sitemap_xml(sub_response.content)
                                    urls.extend(sub_urls)
                                    self.logger.info(f"Found {len(sub_urls)} URLs in {sub_sitemap}")
                            except Exception as e:
                                self.logger.debug(f"Failed to process sub-sitemap {sub_sitemap}: {e}")
                    
                    break  # If we found one sitemap, don't need to try others
                    
            except Exception as e:
                self.logger.debug(f"Failed to fetch sitemap {sitemap_url}: {e}")
                continue
        
        return list(set(urls))  # Remove duplicates
    
    async def _discover_from_navigation(self) -> List[str]:
        """Discover URLs from navigation menus and known blog sections."""
        self.logger.info("Discovering URLs from navigation...")
        
        urls = []
        
        # Known blog sections from our exploration
        known_sections = [
            '/libedge',
            '/microblog', 
            '/blog-archive',
            '/?view=archive'
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for section in known_sections:
                    section_url = urljoin(self.config.site_url, section)
                    section_urls = await self._extract_urls_from_page(browser, section_url)
                    urls.extend(section_urls)
                    self.logger.info(f"Found {len(section_urls)} URLs in {section}")
                    
                    # Small delay between sections
                    await asyncio.sleep(1)
                
            finally:
                await browser.close()
        
        return list(set(urls))
    
    async def _discover_from_archives(self) -> List[str]:
        """Discover URLs from archive pages."""
        self.logger.info("Discovering URLs from archive pages...")
        
        urls = []
        
        # Common archive patterns
        archive_patterns = [
            '/?view=archive',
            '/archive',
            '/blog-archive',
            '/libedge?view=archive'
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for pattern in archive_patterns:
                    archive_url = urljoin(self.config.site_url, pattern)
                    archive_urls = await self._extract_urls_from_page(browser, archive_url)
                    urls.extend(archive_urls)
                    
                    if archive_urls:
                        self.logger.info(f"Found {len(archive_urls)} URLs in archive: {archive_url}")
                        
                        # Try to find "Load More" or pagination
                        more_urls = await self._handle_load_more(browser, archive_url)
                        urls.extend(more_urls)
                    
                    await asyncio.sleep(1)
                
            finally:
                await browser.close()
        
        return list(set(urls))
    
    async def _discover_from_pagination(self) -> List[str]:
        """Discover URLs from paginated blog listings."""
        self.logger.info("Discovering URLs from pagination...")
        
        urls = []
        base_urls = [
            urljoin(self.config.site_url, '/libedge'),
            urljoin(self.config.site_url, '/microblog')
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for base_url in base_urls:
                    # Try page-based pagination
                    page_urls = await self._crawl_pagination(browser, base_url)
                    urls.extend(page_urls)
                    
                    if page_urls:
                        self.logger.info(f"Found {len(page_urls)} URLs via pagination from {base_url}")
                    
                    await asyncio.sleep(1)
                
            finally:
                await browser.close()
        
        return list(set(urls))
    
    async def _discover_from_crawling(self) -> List[str]:
        """Discover URLs by crawling blog sections manually."""
        self.logger.info("Discovering URLs through manual crawling...")
        
        urls = []
        
        # Use the site explorer for this
        explorer = SiteExplorer(self.config)
        discovery_results = await explorer.comprehensive_discovery()
        
        # Extract URLs from all discovery methods
        if discovery_results.get('main_page', {}).get('blog_links'):
            for link in discovery_results['main_page']['blog_links']:
                if link.get('href'):
                    urls.append(link['href'])
        
        if discovery_results.get('navigation', {}).get('navigation_links'):
            for link in discovery_results['navigation']['navigation_links']:
                if link.get('href'):
                    urls.append(link['href'])
        
        return list(set(urls))
    
    async def _extract_urls_from_page(self, browser: Browser, page_url: str) -> List[str]:
        """Extract blog post URLs from a specific page."""
        urls = []
        
        page = await browser.new_page()
        try:
            await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
            
            response = await page.goto(page_url, timeout=30000)
            if not response or response.status != 200:
                return urls
            
            # Wait for content to load
            await page.wait_for_timeout(3000)
            
            # Extract all links
            links = await page.query_selector_all('a[href]')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    if href and self._is_blog_post_url(href):
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            href = urljoin(self.config.site_url, href)
                        elif not href.startswith('http'):
                            href = urljoin(page_url, href)
                        
                        urls.append(href)
                except:
                    continue
            
        except Exception as e:
            self.logger.debug(f"Error extracting URLs from {page_url}: {e}")
        
        finally:
            await page.close()
        
        return list(set(urls))
    
    async def _handle_load_more(self, browser: Browser, page_url: str) -> List[str]:
        """Handle 'Load More' buttons or infinite scroll."""
        urls = []
        
        page = await browser.new_page()
        try:
            await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
            await page.goto(page_url, timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Look for "Load More" button
            load_more_selectors = [
                '.load-more',
                '[data-action="load-more"]',
                '.blog-more-link',
                '.more-posts'
            ]
            
            for selector in load_more_selectors:
                try:
                    load_more_btn = await page.query_selector(selector)
                    if load_more_btn:
                        # Click load more and wait for new content
                        await load_more_btn.click()
                        await page.wait_for_timeout(3000)
                        
                        # Extract new URLs
                        new_links = await page.query_selector_all('a[href]')
                        for link in new_links:
                            href = await link.get_attribute('href')
                            if href and self._is_blog_post_url(href):
                                if href.startswith('/'):
                                    href = urljoin(self.config.site_url, href)
                                urls.append(href)
                        
                        break
                except:
                    continue
            
            # Try infinite scroll
            if not urls:
                try:
                    # Scroll down and see if more content loads
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(3000)
                    
                    # Extract any new URLs
                    links = await page.query_selector_all('a[href]')
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and self._is_blog_post_url(href):
                            if href.startswith('/'):
                                href = urljoin(self.config.site_url, href)
                            urls.append(href)
                except:
                    pass
        
        except Exception as e:
            self.logger.debug(f"Error handling load more for {page_url}: {e}")
        
        finally:
            await page.close()
        
        return list(set(urls))
    
    async def _crawl_pagination(self, browser: Browser, base_url: str) -> List[str]:
        """Crawl through paginated results."""
        urls = []
        
        # Try different pagination patterns
        pagination_patterns = [
            '?page={}',
            '?offset={}',
            '/page/{}',
            '?p={}'
        ]
        
        for pattern in pagination_patterns:
            page_num = 1
            consecutive_failures = 0
            
            while consecutive_failures < 3 and page_num <= 10:  # Limit to 10 pages max
                test_url = base_url + pattern.format(page_num)
                
                page = await browser.new_page()
                try:
                    await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
                    
                    response = await page.goto(test_url, timeout=15000)
                    if response and response.status == 200:
                        # Check if this page has blog posts
                        page_urls = await self._extract_urls_from_page(browser, test_url)
                        
                        if page_urls:
                            urls.extend(page_urls)
                            consecutive_failures = 0
                            self.logger.debug(f"Found {len(page_urls)} URLs on page {page_num}")
                        else:
                            consecutive_failures += 1
                    else:
                        consecutive_failures += 1
                    
                    page_num += 1
                    await asyncio.sleep(1)  # Be respectful
                    
                except Exception as e:
                    self.logger.debug(f"Error crawling page {page_num}: {e}")
                    consecutive_failures += 1
                    page_num += 1
                
                finally:
                    await page.close()
        
        return list(set(urls))
    
    def _parse_sitemap_xml(self, xml_content: bytes) -> List[str]:
        """Parse XML sitemap and extract blog post URLs."""
        urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Handle namespaces
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            # Extract URLs from <url><loc> elements
            for url_elem in root.findall('.//sitemap:url/sitemap:loc', namespaces):
                url = url_elem.text
                if url and self._is_blog_post_url(url):
                    urls.append(url)
            
            # Also try without namespace (some sitemaps don't use it properly)
            if not urls:
                for url_elem in root.findall('.//url/loc'):
                    url = url_elem.text
                    if url and self._is_blog_post_url(url):
                        urls.append(url)
            
        except ET.ParseError as e:
            # Try regex fallback for malformed XML
            self.logger.debug(f"XML parsing failed, trying regex fallback: {e}")
            urls = self._parse_sitemap_regex(xml_content.decode('utf-8', errors='ignore'))
        
        return urls
    
    def _parse_sitemap_regex(self, xml_content: str) -> List[str]:
        """Fallback regex-based sitemap parsing."""
        urls = []
        
        # Extract URLs from <loc> tags
        url_pattern = r'<loc>(.*?)</loc>'
        matches = re.findall(url_pattern, xml_content, re.IGNORECASE)
        
        for match in matches:
            if self._is_blog_post_url(match):
                urls.append(match)
        
        return urls
    
    def _extract_sub_sitemaps(self, xml_content: bytes) -> List[str]:
        """Extract sub-sitemap URLs from sitemap index."""
        sitemaps = []
        
        try:
            root = ET.fromstring(xml_content)
            namespaces = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            for sitemap_elem in root.findall('.//sitemap:sitemap/sitemap:loc', namespaces):
                sitemap_url = sitemap_elem.text
                if sitemap_url:
                    sitemaps.append(sitemap_url)
            
            # Try without namespace
            if not sitemaps:
                for sitemap_elem in root.findall('.//sitemap/loc'):
                    sitemap_url = sitemap_elem.text
                    if sitemap_url:
                        sitemaps.append(sitemap_url)
        
        except ET.ParseError:
            # Regex fallback
            sitemap_pattern = r'<sitemap>.*?<loc>(.*?)</loc>.*?</sitemap>'
            matches = re.findall(sitemap_pattern, xml_content.decode('utf-8', errors='ignore'), re.DOTALL | re.IGNORECASE)
            sitemaps.extend(matches)
        
        return sitemaps
    
    def _is_blog_post_url(self, url: str) -> bool:
        """Determine if a URL looks like a blog post."""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Positive indicators
        blog_indicators = [
            '/libedge/',  # Main blog section
            '/microblog/',  # Microblog section
        ]
        
        # Negative indicators
        negative_indicators = [
            '/admin', '/login', '/contact', '/about', '/home',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
            'mailto:', 'tel:', '#', 'javascript:',
            '/libedge?', '/libedge$', '/microblog?', '/microblog$'  # Avoid index pages
        ]
        
        # Check negative indicators first
        if any(neg in url_lower for neg in negative_indicators):
            return False
        
        # Check positive indicators
        if any(pos in url_lower for pos in blog_indicators):
            # Additional validation: should have more path segments (actual posts)
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            # For this blog, posts have pattern: /libedge/YYYY/MM/DD/title
            if len(path_parts) >= 5:  # ['libedge', 'YYYY', 'MM', 'DD', 'title']
                return True
        
        return False
    
    def _filter_and_validate_urls(self, urls: List[str]) -> List[str]:
        """Filter and validate discovered URLs."""
        valid_urls = []
        seen_urls = set()
        
        for url in urls:
            # Skip if already seen
            if url in seen_urls:
                continue
            
            # Basic URL validation
            if not url or not url.startswith('http'):
                continue
            
            # Check if it's a valid blog post URL
            if not self._is_blog_post_url(url):
                continue
            
            # Normalize URL (remove fragments, etc.)
            parsed = urlparse(url)
            normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            if normalized_url not in seen_urls:
                valid_urls.append(normalized_url)
                seen_urls.add(normalized_url)
        
        # Sort URLs for consistent ordering
        valid_urls.sort()
        
        return valid_urls