"""Content extraction engine for blog posts."""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from datetime import datetime
import json
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import requests
from dateutil import parser as date_parser

from .config import ArchiveConfig
from .logger import ProgressLogger


class ContentExtractor:
    """Extracts content from blog posts with comprehensive metadata."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.extractor")
        
        # Set up requests session for non-JS content
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.scraping.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    async def extract_posts_from_urls(self, post_urls: List[str]) -> List[Dict[str, Any]]:
        """Extract content from a list of blog post URLs."""
        self.logger.info(f"Starting content extraction for {len(post_urls)} posts")
        
        progress = ProgressLogger(self.logger, len(post_urls), "Extracting posts")
        extracted_posts = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for i, url in enumerate(post_urls):
                    try:
                        # Add delay between requests
                        if i > 0:
                            await asyncio.sleep(self.config.scraping.delay_between_requests)
                        
                        post_data = await self._extract_single_post(browser, url)
                        if post_data:
                            extracted_posts.append(post_data)
                            self.logger.debug(f"Successfully extracted: {post_data.get('title', url)}")
                        else:
                            self.logger.warning(f"Failed to extract content from: {url}")
                        
                        progress.update()
                        
                    except Exception as e:
                        self.logger.error(f"Error extracting {url}: {e}")
                        progress.update()
                        continue
                
                progress.complete()
                
            finally:
                await browser.close()
        
        self.logger.info(f"Content extraction complete. Successfully extracted {len(extracted_posts)} posts")
        return extracted_posts
    
    async def _extract_single_post(self, browser: Browser, url: str) -> Optional[Dict[str, Any]]:
        """Extract content from a single blog post."""
        page = await browser.new_page()
        
        try:
            await page.set_extra_http_headers({'User-Agent': self.config.scraping.user_agent})
            
            # Navigate to the post
            response = await page.goto(url, timeout=30000)
            if not response or response.status != 200:
                self.logger.warning(f"Failed to load {url}: HTTP {response.status if response else 'No response'}")
                return None
            
            # Wait for content to load
            await page.wait_for_timeout(3000)
            
            # Extract post data
            post_data = {
                'url': url,
                'scraped_at': datetime.now().isoformat(),
                'id': self._generate_post_id(url),
                'slug': self._extract_slug_from_url(url)
            }
            
            # Extract basic metadata
            post_data.update(await self._extract_basic_metadata(page))
            
            # Extract content
            post_data.update(await self._extract_post_content(page))
            
            # Extract dates
            post_data.update(await self._extract_dates(page, url))
            
            # Extract categories and tags
            post_data.update(await self._extract_taxonomy(page))
            
            # Extract images
            post_data['images'] = await self._extract_images(page)
            
            # Extract links
            post_data['links'] = await self._extract_links(page)
            
            # Validate and clean data
            post_data = self._validate_and_clean_post_data(post_data)
            
            return post_data
            
        except Exception as e:
            self.logger.error(f"Error extracting post {url}: {e}")
            return None
            
        finally:
            await page.close()
    
    async def _extract_basic_metadata(self, page: Page) -> Dict[str, Any]:
        """Extract basic metadata like title, description, etc."""
        metadata = {}
        
        try:
            # Title - try multiple selectors
            title_selectors = [
                'h1.entry-title',
                '.entry-header h1',
                '.blog-item-title',
                'h1',
                'title'
            ]
            
            title = None
            for selector in title_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        title = await element.inner_text()
                        if title and title.strip():
                            break
                except:
                    continue
            
            if not title:
                title = await page.title()
            
            metadata['title'] = title.strip() if title else 'Untitled'
            
            # Meta description
            meta_desc = await page.get_attribute('meta[name="description"]', 'content')
            metadata['meta_description'] = meta_desc.strip() if meta_desc else ''
            
            # Author - try multiple approaches
            author = await self._extract_author(page)
            metadata['author'] = author
            
        except Exception as e:
            self.logger.warning(f"Error extracting basic metadata: {e}")
        
        return metadata
    
    async def _extract_post_content(self, page: Page) -> Dict[str, Any]:
        """Extract the main post content in multiple formats."""
        content_data = {}
        
        try:
            # Try multiple content selectors (Squarespace patterns)
            content_selectors = [
                '.blog-item-content-wrapper',
                '.entry-content',
                '.blog-item-wrapper .sqs-block-content',
                '.blog-basic-grid--text',
                'article .entry-content',
                '.post-content',
                '.content'
            ]
            
            content_html = None
            content_element = None
            
            for selector in content_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        html = await element.inner_html()
                        if html and len(html.strip()) > 50:  # Ensure substantial content
                            content_html = html
                            content_element = element
                            break
                except:
                    continue
            
            if not content_html:
                # Fallback: try to get body content
                body = await page.query_selector('body')
                if body:
                    content_html = await body.inner_html()
            
            # Process HTML content
            if content_html:
                # Clean HTML with BeautifulSoup
                soup = BeautifulSoup(content_html, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get cleaned HTML
                content_data['content_html'] = str(soup)
                
                # Extract plain text
                content_data['content_text'] = soup.get_text().strip()
                
                # Convert to markdown (basic conversion)
                content_data['content_markdown'] = self._html_to_markdown(soup)
                
                # Generate excerpt
                content_data['excerpt'] = self._generate_excerpt(soup.get_text())
                
                # Count words
                content_data['word_count'] = len(soup.get_text().split())
            
        except Exception as e:
            self.logger.warning(f"Error extracting content: {e}")
        
        return content_data
    
    async def _extract_dates(self, page: Page, url: str) -> Dict[str, Any]:
        """Extract publication and modification dates."""
        dates = {}
        
        try:
            # Try to extract from URL first (most reliable for this site)
            url_date = self._extract_date_from_url(url)
            if url_date:
                dates['published_date'] = url_date.isoformat()
            
            # Try meta tags
            published_meta = await page.get_attribute('meta[property="article:published_time"]', 'content')
            if published_meta:
                try:
                    parsed_date = date_parser.parse(published_meta)
                    dates['published_date'] = parsed_date.isoformat()
                except:
                    pass
            
            modified_meta = await page.get_attribute('meta[property="article:modified_time"]', 'content')
            if modified_meta:
                try:
                    parsed_date = date_parser.parse(modified_meta)
                    dates['modified_date'] = parsed_date.isoformat()
                except:
                    pass
            
            # Try structured data
            structured_data = await self._extract_structured_data(page)
            if structured_data:
                if 'datePublished' in structured_data:
                    try:
                        parsed_date = date_parser.parse(structured_data['datePublished'])
                        dates['published_date'] = parsed_date.isoformat()
                    except:
                        pass
                
                if 'dateModified' in structured_data:
                    try:
                        parsed_date = date_parser.parse(structured_data['dateModified'])
                        dates['modified_date'] = parsed_date.isoformat()
                    except:
                        pass
            
            # Try to find date in content
            if 'published_date' not in dates:
                date_text = await self._find_date_in_content(page)
                if date_text:
                    dates['published_date'] = date_text.isoformat()
        
        except Exception as e:
            self.logger.warning(f"Error extracting dates: {e}")
        
        return dates
    
    async def _extract_taxonomy(self, page: Page) -> Dict[str, Any]:
        """Extract categories, tags, and other taxonomy."""
        taxonomy = {
            'categories': [],
            'tags': []
        }
        
        try:
            # Look for category/tag elements
            category_selectors = [
                '.blog-meta-item .category',
                '.categories a',
                '.cat-links a',
                '[rel="category tag"]'
            ]
            
            for selector in category_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip():
                            taxonomy['categories'].append(text.strip())
                except:
                    continue
            
            # Look for tags
            tag_selectors = [
                '.blog-meta-item .tag',
                '.tags a',
                '.tag-links a',
                '[rel="tag"]'
            ]
            
            for selector in tag_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip():
                            taxonomy['tags'].append(text.strip())
                except:
                    continue
            
            # Remove duplicates
            taxonomy['categories'] = list(set(taxonomy['categories']))
            taxonomy['tags'] = list(set(taxonomy['tags']))
        
        except Exception as e:
            self.logger.warning(f"Error extracting taxonomy: {e}")
        
        return taxonomy
    
    async def _extract_images(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all images from the post."""
        images = []
        
        try:
            # Find all images in content
            img_elements = await page.query_selector_all('img')
            
            for img in img_elements:
                try:
                    src = await img.get_attribute('src')
                    if not src:
                        continue
                    
                    # Convert relative URLs to absolute
                    if src.startswith('/'):
                        src = urljoin(self.config.site_url, src)
                    elif not src.startswith('http'):
                        src = urljoin(page.url, src)
                    
                    # Skip small/icon images
                    width = await img.get_attribute('width')
                    height = await img.get_attribute('height')
                    
                    if width and height:
                        try:
                            if int(width) < 50 or int(height) < 50:
                                continue
                        except:
                            pass
                    
                    # Get image metadata
                    alt_text = await img.get_attribute('alt') or ''
                    title = await img.get_attribute('title') or ''
                    
                    # Try to find caption (common patterns)
                    caption = ''
                    parent = await img.evaluate('el => el.parentElement')
                    if parent:
                        caption_selectors = ['.caption', '.wp-caption-text', 'figcaption']
                        for selector in caption_selectors:
                            try:
                                caption_elem = await parent.query_selector(selector)
                                if caption_elem:
                                    caption = await caption_elem.inner_text()
                                    break
                            except:
                                continue
                    
                    images.append({
                        'original_url': src,
                        'alt_text': alt_text,
                        'title': title,
                        'caption': caption,
                        'width': width,
                        'height': height
                    })
                
                except Exception as e:
                    self.logger.debug(f"Error processing image: {e}")
                    continue
        
        except Exception as e:
            self.logger.warning(f"Error extracting images: {e}")
        
        return images
    
    async def _extract_links(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all links from the post content."""
        links = []
        
        try:
            # Find all links in content area
            content_selectors = [
                '.blog-item-content-wrapper a',
                '.entry-content a',
                'article a'
            ]
            
            link_elements = []
            for selector in content_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    link_elements.extend(elements)
                    if elements:  # If we found links with this selector, we're good
                        break
                except:
                    continue
            
            # If no content-specific links found, get all links
            if not link_elements:
                link_elements = await page.query_selector_all('a[href]')
            
            for link in link_elements:
                try:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    title = await link.get_attribute('title')
                    
                    if href and href not in ['#', 'javascript:void(0)']:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            href = urljoin(self.config.site_url, href)
                        elif not href.startswith(('http', 'mailto:', 'tel:')):
                            href = urljoin(page.url, href)
                        
                        # Classify link type
                        link_type = self._classify_link(href)
                        
                        links.append({
                            'url': href,
                            'text': text.strip() if text else '',
                            'title': title or '',
                            'type': link_type
                        })
                
                except Exception as e:
                    self.logger.debug(f"Error processing link: {e}")
                    continue
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_links = []
            for link in links:
                if link['url'] not in seen_urls:
                    unique_links.append(link)
                    seen_urls.add(link['url'])
            
            return unique_links
        
        except Exception as e:
            self.logger.warning(f"Error extracting links: {e}")
            return []
    
    async def _extract_author(self, page: Page) -> str:
        """Extract author information."""
        author_selectors = [
            '.blog-meta-item .author',
            '.entry-author',
            '.by-author',
            '.author-name',
            'meta[name="author"]'
        ]
        
        for selector in author_selectors:
            try:
                if selector.startswith('meta'):
                    author = await page.get_attribute(selector, 'content')
                else:
                    element = await page.query_selector(selector)
                    if element:
                        author = await element.inner_text()
                
                if author and author.strip():
                    return author.strip()
            except:
                continue
        
        return "Katie Day"  # Default author for this blog
    
    async def _extract_structured_data(self, page: Page) -> Optional[Dict[str, Any]]:
        """Extract structured data (JSON-LD) from the page."""
        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                content = await script.inner_text()
                if content:
                    try:
                        data = json.loads(content)
                        if isinstance(data, dict) and data.get('@type') in ['BlogPosting', 'Article']:
                            return data
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.debug(f"Error extracting structured data: {e}")
        
        return None
    
    async def _find_date_in_content(self, page: Page) -> Optional[datetime]:
        """Try to find a date in the page content."""
        try:
            # Look for date patterns in common areas
            date_selectors = [
                '.blog-meta .date',
                '.entry-date',
                '.post-date',
                'time[datetime]'
            ]
            
            for selector in date_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        if selector.endswith('[datetime]'):
                            date_str = await element.get_attribute('datetime')
                        else:
                            date_str = await element.inner_text()
                        
                        if date_str:
                            return date_parser.parse(date_str)
                except:
                    continue
        except Exception as e:
            self.logger.debug(f"Error finding date in content: {e}")
        
        return None
    
    def _generate_post_id(self, url: str) -> str:
        """Generate a unique ID for the post based on URL."""
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        if len(path_parts) >= 4:
            # For URLs like /libedge/2019/10/26/post-title
            return f"{path_parts[1]}-{path_parts[2]}-{path_parts[3]}-{path_parts[4]}"
        else:
            # Fallback: use the last part of the path
            return path_parts[-1] if path_parts else 'unknown'
    
    def _extract_slug_from_url(self, url: str) -> str:
        """Extract the slug from the URL."""
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        return path_parts[-1] if path_parts else ''
    
    def _extract_date_from_url(self, url: str) -> Optional[datetime]:
        """Extract date from URL pattern like /libedge/2019/10/26/post-title."""
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            # Look for date pattern: year/month/day
            if len(path_parts) >= 4:
                year_str, month_str, day_str = path_parts[1:4]
                
                # Validate that these look like date components
                if (year_str.isdigit() and len(year_str) == 4 and
                    month_str.isdigit() and 1 <= int(month_str) <= 12 and
                    day_str.isdigit() and 1 <= int(day_str) <= 31):
                    
                    return datetime(int(year_str), int(month_str), int(day_str))
        
        except Exception as e:
            self.logger.debug(f"Error extracting date from URL {url}: {e}")
        
        return None
    
    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        """Basic HTML to Markdown conversion."""
        # This is a simple conversion - could be enhanced with a proper library
        text = soup.get_text()
        
        # Basic markdown formatting
        for h1 in soup.find_all('h1'):
            text = text.replace(h1.get_text(), f"# {h1.get_text()}")
        
        for h2 in soup.find_all('h2'):
            text = text.replace(h2.get_text(), f"## {h2.get_text()}")
        
        for h3 in soup.find_all('h3'):
            text = text.replace(h3.get_text(), f"### {h3.get_text()}")
        
        return text
    
    def _generate_excerpt(self, text: str, max_length: int = 300) -> str:
        """Generate an excerpt from the text content."""
        if len(text) <= max_length:
            return text
        
        # Find the last complete sentence within the limit
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        
        if last_period > max_length * 0.7:  # If we can keep most of the text
            return truncated[:last_period + 1]
        else:
            return truncated + "..."
    
    def _classify_link(self, url: str) -> str:
        """Classify the type of link."""
        url_lower = url.lower()
        
        if url_lower.startswith('mailto:'):
            return 'email'
        elif url_lower.startswith('tel:'):
            return 'phone'
        elif self.config.site_url.lower() in url_lower:
            return 'internal'
        else:
            return 'external'
    
    def _validate_and_clean_post_data(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean the extracted post data."""
        # Ensure required fields exist
        if 'title' not in post_data or not post_data['title']:
            post_data['title'] = f"Post {post_data.get('id', 'Unknown')}"
        
        # Clean up empty fields
        for key in ['meta_description', 'excerpt', 'content_text', 'content_html', 'content_markdown']:
            if key in post_data and not post_data[key]:
                post_data[key] = ''
        
        # Ensure lists exist
        for key in ['categories', 'tags', 'images', 'links']:
            if key not in post_data:
                post_data[key] = []
        
        # Add extracted timestamp
        post_data['extracted_at'] = datetime.now().isoformat()
        
        return post_data