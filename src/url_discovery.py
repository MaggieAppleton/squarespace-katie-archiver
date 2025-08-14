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
        
        # Method 6: Historical year-based discovery (2005-2014)
        historical_urls = await self._discover_historical_posts()
        discovery_results['historical_urls'] = historical_urls
        discovery_results['discovery_methods']['historical'] = len(historical_urls)
        self.discovered_urls.update(historical_urls)
        
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
        """Discover URLs from sitemap.xml and alternative locations."""
        self.logger.info("Discovering URLs from sitemap...")
        
        urls = []
        # Try multiple sitemap locations and patterns
        sitemap_urls = [
            urljoin(self.config.site_url, '/sitemap.xml'),
            urljoin(self.config.site_url, '/sitemap_index.xml'),
            urljoin(self.config.site_url, '/sitemap-posts.xml'),
            urljoin(self.config.site_url, '/sitemap-blog.xml'),
            urljoin(self.config.site_url, '/sitemap/posts.xml'),
            urljoin(self.config.site_url, '/sitemap/blog.xml'),
            urljoin(self.config.site_url, '/sitemaps/sitemap.xml'),
            urljoin(self.config.site_url, '/blog-sitemap.xml'),
            urljoin(self.config.site_url, '/posts-sitemap.xml'),
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
                    
                    # Don't break here - try all sitemaps to be comprehensive
                    
            except Exception as e:
                self.logger.debug(f"Failed to fetch sitemap {sitemap_url}: {e}")
                continue
        
        # Also try to discover URLs from RSS feeds
        rss_urls = await self._discover_from_rss_feeds()
        urls.extend(rss_urls)
        
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
        """Crawl through paginated results with enhanced historical discovery."""
        urls = []
        
        # Try different pagination patterns with more aggressive limits for historical content
        pagination_patterns = [
            '?page={}',
            '?offset={}',
            '/page/{}',
            '?p={}',
            '?start={}',  # Alternative pagination
            '&page={}',   # For URLs that already have query params
        ]
        
        for pattern in pagination_patterns:
            page_num = 1
            consecutive_failures = 0
            max_pages = 25  # Increased from 10 to catch more historical content
            
            while consecutive_failures < 5 and page_num <= max_pages:  # Allow more failures
                # Handle both base URLs with and without existing query params
                if '?' in base_url and pattern.startswith('?'):
                    test_url = base_url + pattern.replace('?', '&', 1).format(page_num)
                else:
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
                            
                            # Check if we're finding older content (pre-2015)
                            old_content = [url for url in page_urls if any(f'/{year}/' in url for year in range(2005, 2015))]
                            if old_content:
                                self.logger.info(f"Found {len(old_content)} historical URLs on page {page_num} of {base_url}")
                            else:
                                self.logger.debug(f"Found {len(page_urls)} URLs on page {page_num}")
                        else:
                            consecutive_failures += 1
                    else:
                        consecutive_failures += 1
                    
                    page_num += 1
                    await asyncio.sleep(0.8)  # Slightly reduced delay for efficiency
                    
                except Exception as e:
                    self.logger.debug(f"Error crawling page {page_num}: {e}")
                    consecutive_failures += 1
                    page_num += 1
                
                finally:
                    await page.close()
                
                # If we've gone through many pages without finding anything, try next pattern
                if page_num > 15 and consecutive_failures >= 3:
                    break
        
        return list(set(urls))
    
    async def _discover_from_rss_feeds(self) -> List[str]:
        """Discover URLs from RSS/Atom feeds which may contain historical content."""
        self.logger.info("Discovering URLs from RSS/Atom feeds...")
        
        urls = []
        # Common RSS/Atom feed locations
        feed_urls = [
            urljoin(self.config.site_url, '/rss'),
            urljoin(self.config.site_url, '/feed'),
            urljoin(self.config.site_url, '/feeds'),
            urljoin(self.config.site_url, '/atom.xml'),
            urljoin(self.config.site_url, '/rss.xml'),
            urljoin(self.config.site_url, '/feed.xml'),
            urljoin(self.config.site_url, '/blog/rss'),
            urljoin(self.config.site_url, '/blog/feed'),
            urljoin(self.config.site_url, '/libedge/rss'),
            urljoin(self.config.site_url, '/libedge/feed'),
            urljoin(self.config.site_url, '/microblog/rss'),
            urljoin(self.config.site_url, '/microblog/feed'),
            urljoin(self.config.site_url, '/blog.rss'),
            urljoin(self.config.site_url, '/?format=rss'),
            urljoin(self.config.site_url, '/libedge?format=rss'),
            urljoin(self.config.site_url, '/microblog?format=rss'),
        ]
        
        for feed_url in feed_urls:
            try:
                response = self.session.get(feed_url, timeout=30)
                if response.status_code == 200:
                    feed_urls_found = self._parse_rss_feed_for_urls(response.content)
                    if feed_urls_found:
                        urls.extend(feed_urls_found)
                        self.logger.info(f"Found {len(feed_urls_found)} URLs in RSS feed: {feed_url}")
                        
            except Exception as e:
                self.logger.debug(f"Failed to fetch RSS feed {feed_url}: {e}")
                continue
        
        return list(set(urls))
    
    def _parse_rss_feed_for_urls(self, feed_content: bytes) -> List[str]:
        """Parse RSS/Atom feed content for blog post URLs."""
        urls = []
        
        try:
            # Convert to string
            content = feed_content.decode('utf-8', errors='ignore')
            
            # Look for <link> tags in RSS and <id> tags in Atom feeds
            import re
            
            # RSS <link> tags
            rss_pattern = r'<link[^>]*>([^<]+)</link>'
            rss_matches = re.findall(rss_pattern, content, re.IGNORECASE)
            for match in rss_matches:
                match = match.strip()
                if self._is_blog_post_url(match):
                    urls.append(match)
            
            # Atom <id> and <link> tags  
            atom_id_pattern = r'<id[^>]*>([^<]+)</id>'
            atom_matches = re.findall(atom_id_pattern, content, re.IGNORECASE)
            for match in atom_matches:
                match = match.strip()
                if self._is_blog_post_url(match):
                    urls.append(match)
            
            # Atom link href attributes
            atom_link_pattern = r'<link[^>]+href=["\']([^"\']+)["\'][^>]*>'
            atom_link_matches = re.findall(atom_link_pattern, content, re.IGNORECASE)
            for match in atom_link_matches:
                match = match.strip()
                if self._is_blog_post_url(match):
                    urls.append(match)
                    
        except Exception as e:
            self.logger.warning(f"Error parsing RSS/Atom feed: {e}")
        
        return urls
    
    async def _discover_historical_posts(self) -> List[str]:
        """Discover historical posts from 2005-2014 using year-based exploration."""
        self.logger.info("Discovering historical posts (2005-2014)...")
        
        urls = []
        historical_years = range(2005, 2015)  # 2005-2014
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for year in historical_years:
                    # Try different historical URL patterns
                    year_patterns = [
                        f'/libedge/{year}',
                        f'/libedge?year={year}',
                        f'/libedge?archive={year}',
                        f'/libedge/?year={year}',
                        f'/blog/{year}',
                        f'/blog?year={year}'
                    ]
                    
                    for pattern in year_patterns:
                        year_url = urljoin(self.config.site_url, pattern)
                        
                        try:
                            year_urls = await self._extract_urls_from_page(browser, year_url)
                            if year_urls:
                                urls.extend(year_urls)
                                self.logger.info(f"Found {len(year_urls)} URLs for year {year} via {pattern}")
                                
                                # Also try to paginate within the year
                                paginated_urls = await self._paginate_year_archive(browser, year_url, year)
                                urls.extend(paginated_urls)
                                
                                break  # If we found content for this year, don't try other patterns
                        except Exception as e:
                            self.logger.debug(f"Failed to explore {year_url}: {e}")
                            continue
                    
                    # Small delay between years
                    await asyncio.sleep(1)
                
                # Also try the general archive with different sort orders
                archive_urls = await self._try_archive_sorting()
                urls.extend(archive_urls)
                
            finally:
                await browser.close()
        
        return list(set(urls))
    
    async def _paginate_year_archive(self, browser: Browser, base_url: str, year: int) -> List[str]:
        """Paginate through a specific year's archive."""
        urls = []
        
        pagination_patterns = [
            f'?year={year}&page={{}}',
            f'?year={year}&offset={{}}',
            f'?page={{}}',
            f'&page={{}}'
        ]
        
        for pattern in pagination_patterns:
            page_num = 2  # Start with page 2 since we already got page 1
            consecutive_failures = 0
            
            while consecutive_failures < 3 and page_num <= 10:  # Limit to 10 pages
                if '{}' in pattern:
                    test_url = base_url + pattern.format(page_num)
                else:
                    test_url = f"{base_url}{pattern}{page_num}"
                
                page = await browser.new_page()
                try:
                    await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
                    
                    response = await page.goto(test_url, timeout=15000)
                    if response and response.status == 200:
                        page_urls = await self._extract_urls_from_page(browser, test_url)
                        
                        if page_urls:
                            urls.extend(page_urls)
                            consecutive_failures = 0
                            self.logger.debug(f"Found {len(page_urls)} URLs on year {year} page {page_num}")
                        else:
                            consecutive_failures += 1
                    else:
                        consecutive_failures += 1
                    
                    page_num += 1
                    await asyncio.sleep(0.5)  # Small delay
                    
                except Exception as e:
                    self.logger.debug(f"Error paginating year {year} page {page_num}: {e}")
                    consecutive_failures += 1
                    page_num += 1
                
                finally:
                    await page.close()
            
            if urls:  # If we found URLs with this pattern, don't try others
                break
        
        return list(set(urls))
    
    async def _try_archive_sorting(self) -> List[str]:
        """Try different sorting options on archive pages to find older content."""
        self.logger.info("Trying different archive sorting options...")
        
        urls = []
        archive_sort_patterns = [
            '/libedge?view=archive&sort=date',
            '/libedge?view=archive&sort=oldest',
            '/libedge?view=archive&order=asc',
            '/libedge?view=archive&sort=published&order=asc',
            '/libedge?archive=true&sort=date',
            '/blog-archive?sort=oldest',
            '/blog-archive?order=asc'
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for pattern in archive_sort_patterns:
                    archive_url = urljoin(self.config.site_url, pattern)
                    
                    try:
                        page_urls = await self._extract_urls_from_page(browser, archive_url)
                        if page_urls:
                            urls.extend(page_urls)
                            self.logger.info(f"Found {len(page_urls)} URLs with sorting: {pattern}")
                            
                            # Try to paginate this sorted view
                            paginated_urls = await self._crawl_pagination(browser, archive_url)
                            urls.extend(paginated_urls)
                    
                    except Exception as e:
                        self.logger.debug(f"Failed to try sorting {pattern}: {e}")
                        continue
                    
                    await asyncio.sleep(1)
                
            finally:
                await browser.close()
        
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
            
            # Enhanced pattern matching for different URL structures:
            # Modern posts: /libedge/YYYY/MM/DD/title (5+ parts)
            # Older posts might have: /libedge/YYYY/title or /libedge/title or other variations
            if len(path_parts) >= 3:  # At minimum: ['libedge', year_or_title, something]
                # Check if this looks like a real post (has a slug-like final part)
                if len(path_parts) >= 2:
                    last_part = path_parts[-1]
                    # Look for slug patterns (words with hyphens) or reasonable titles
                    if (len(last_part) > 3 and 
                        ('-' in last_part or len(last_part.split('-')) > 1 or 
                         any(char.isalpha() for char in last_part))):
                        return True
                
                # Also accept the standard 5-part pattern
                if len(path_parts) >= 5:
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