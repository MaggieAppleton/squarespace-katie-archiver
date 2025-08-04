"""Data validation and cleaning for extracted blog posts."""

import logging
import re
from typing import List, Dict, Any, Set, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse
import json

from dateutil import parser as date_parser


class DataValidator:
    """Validates and cleans extracted blog post data."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.validator")
        
        # Validation statistics
        self.validation_stats = {
            'total_posts': 0,
            'valid_posts': 0,
            'issues_found': 0,
            'fixes_applied': 0,
            'warnings': 0,
            'errors': 0
        }
        
        # Issue tracking
        self.issues = []
    
    def validate_and_clean_posts(self, posts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Validate and clean a list of blog posts."""
        self.logger.info(f"Starting validation and cleaning of {len(posts)} posts...")
        
        self.validation_stats['total_posts'] = len(posts)
        validated_posts = []
        
        for i, post in enumerate(posts):
            try:
                validated_post = self._validate_single_post(post, i)
                if validated_post:
                    validated_posts.append(validated_post)
                    self.validation_stats['valid_posts'] += 1
                else:
                    self.validation_stats['errors'] += 1
                    self.logger.error(f"Post {i} failed validation completely")
            
            except Exception as e:
                self.validation_stats['errors'] += 1
                self.logger.error(f"Error validating post {i}: {e}")
                continue
        
        # Generate validation report
        validation_report = self._generate_validation_report()
        
        self.logger.info(f"Validation complete. {self.validation_stats['valid_posts']}/{self.validation_stats['total_posts']} posts passed")
        
        return validated_posts, validation_report
    
    def _validate_single_post(self, post: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        """Validate and clean a single blog post."""
        # Create a copy to avoid modifying the original
        validated_post = post.copy()
        post_issues = []
        
        # 1. Validate required fields
        required_fields = ['url', 'title', 'id']
        for field in required_fields:
            if field not in validated_post or not validated_post[field]:
                issue = f"Missing required field: {field}"
                post_issues.append(issue)
                self.logger.error(f"Post {index}: {issue}")
                
                # Try to fix
                if field == 'title':
                    validated_post[field] = f"Untitled Post {index}"
                    self.validation_stats['fixes_applied'] += 1
                elif field == 'id':
                    validated_post[field] = f"post-{index}"
                    self.validation_stats['fixes_applied'] += 1
        
        # Skip post if URL is missing (can't fix this)
        if not validated_post.get('url'):
            return None
        
        # 2. Validate and clean URL
        validated_post['url'] = self._validate_url(validated_post['url'], index, post_issues)
        
        # 3. Validate and clean title
        validated_post['title'] = self._validate_title(validated_post.get('title', ''), index, post_issues)
        
        # 4. Validate and clean dates
        validated_post = self._validate_dates(validated_post, index, post_issues)
        
        # 5. Validate and clean content
        validated_post = self._validate_content(validated_post, index, post_issues)
        
        # 6. Validate and clean metadata
        validated_post = self._validate_metadata(validated_post, index, post_issues)
        
        # 7. Validate and clean images
        validated_post['images'] = self._validate_images(validated_post.get('images', []), index, post_issues)
        
        # 8. Validate and clean links
        validated_post['links'] = self._validate_links(validated_post.get('links', []), index, post_issues)
        
        # 9. Validate and clean taxonomy
        validated_post = self._validate_taxonomy(validated_post, index, post_issues)
        
        # 10. Add validation metadata
        validated_post['validation'] = {
            'validated_at': datetime.now().isoformat(),
            'issues_found': len(post_issues),
            'issues': post_issues
        }
        
        # Update statistics
        if post_issues:
            self.validation_stats['issues_found'] += len(post_issues)
            self.validation_stats['warnings'] += 1
            self.issues.extend([f"Post {index}: {issue}" for issue in post_issues])
        
        return validated_post
    
    def _validate_url(self, url: str, index: int, issues: List[str]) -> str:
        """Validate and clean URL."""
        if not url:
            issues.append("URL is empty")
            return ""
        
        # Check if URL is valid
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                issues.append(f"Invalid URL format: {url}")
        except Exception as e:
            issues.append(f"URL parsing error: {e}")
        
        # Normalize URL
        cleaned_url = url.strip()
        
        # Convert HTTP to HTTPS if this is the site's domain
        if cleaned_url.startswith('http://') and self.config.site_url.startswith('https://'):
            site_domain = urlparse(self.config.site_url).netloc
            url_domain = urlparse(cleaned_url).netloc
            if site_domain == url_domain:
                cleaned_url = cleaned_url.replace('http://', 'https://', 1)
                self.validation_stats['fixes_applied'] += 1
        
        return cleaned_url
    
    def _validate_title(self, title: str, index: int, issues: List[str]) -> str:
        """Validate and clean title."""
        if not title or not title.strip():
            issues.append("Title is empty")
            title = f"Untitled Post {index}"
            self.validation_stats['fixes_applied'] += 1
        
        # Clean title
        cleaned_title = title.strip()
        
        # Remove excessive whitespace
        cleaned_title = re.sub(r'\s+', ' ', cleaned_title)
        
        # Check for overly long titles
        if len(cleaned_title) > 200:
            issues.append(f"Title is very long ({len(cleaned_title)} characters)")
            cleaned_title = cleaned_title[:197] + "..."
            self.validation_stats['fixes_applied'] += 1
        
        # Check for HTML in title
        if '<' in cleaned_title and '>' in cleaned_title:
            issues.append("Title contains HTML tags")
            # Basic HTML stripping
            cleaned_title = re.sub(r'<[^>]+>', '', cleaned_title)
            self.validation_stats['fixes_applied'] += 1
        
        return cleaned_title
    
    def _validate_dates(self, post: Dict[str, Any], index: int, issues: List[str]) -> Dict[str, Any]:
        """Validate and clean date fields."""
        date_fields = ['published_date', 'modified_date', 'scraped_at', 'extracted_at']
        
        for field in date_fields:
            if field in post:
                cleaned_date = self._validate_single_date(post[field], field, index, issues)
                if cleaned_date:
                    post[field] = cleaned_date
                else:
                    # Remove invalid date
                    del post[field]
        
        # Ensure published_date exists
        if 'published_date' not in post:
            # Try to extract from URL or use current date as fallback
            url_date = self._extract_date_from_url(post.get('url', ''))
            if url_date:
                post['published_date'] = url_date.isoformat()
                self.validation_stats['fixes_applied'] += 1
            else:
                issues.append("No published date found")
        
        return post
    
    def _validate_single_date(self, date_value: Any, field_name: str, index: int, issues: List[str]) -> Optional[str]:
        """Validate a single date value."""
        if not date_value:
            return None
        
        # If already a string in ISO format, validate it
        if isinstance(date_value, str):
            try:
                parsed_date = date_parser.parse(date_value)
                return parsed_date.isoformat()
            except Exception as e:
                issues.append(f"Invalid date format in {field_name}: {date_value}")
                return None
        
        # If datetime object, convert to ISO string
        if isinstance(date_value, datetime):
            return date_value.isoformat()
        
        issues.append(f"Unknown date type in {field_name}: {type(date_value)}")
        return None
    
    def _validate_content(self, post: Dict[str, Any], index: int, issues: List[str]) -> Dict[str, Any]:
        """Validate and clean content fields."""
        content_fields = ['content_html', 'content_text', 'content_markdown', 'excerpt']
        
        for field in content_fields:
            if field in post:
                content = post[field]
                
                if not isinstance(content, str):
                    issues.append(f"{field} is not a string")
                    post[field] = str(content) if content else ""
                    self.validation_stats['fixes_applied'] += 1
                
                # Clean excessive whitespace
                if content:
                    cleaned_content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Max 2 consecutive newlines
                    cleaned_content = cleaned_content.strip()
                    
                    if cleaned_content != content:
                        post[field] = cleaned_content
                        self.validation_stats['fixes_applied'] += 1
        
        # Ensure we have some content
        has_content = any(post.get(field) for field in ['content_html', 'content_text'])
        if not has_content:
            issues.append("Post has no content")
        
        # Validate word count
        word_count = post.get('word_count', 0)
        if word_count == 0 and post.get('content_text'):
            actual_count = len(post['content_text'].split())
            post['word_count'] = actual_count
            self.validation_stats['fixes_applied'] += 1
        elif isinstance(word_count, str):
            try:
                post['word_count'] = int(word_count)
                self.validation_stats['fixes_applied'] += 1
            except ValueError:
                post['word_count'] = 0
                issues.append("Invalid word count format")
        
        return post
    
    def _validate_metadata(self, post: Dict[str, Any], index: int, issues: List[str]) -> Dict[str, Any]:
        """Validate and clean metadata fields."""
        # Validate author
        if 'author' not in post or not post['author']:
            post['author'] = "Katie Day"  # Default author for this blog
            self.validation_stats['fixes_applied'] += 1
        
        # Validate slug
        if 'slug' not in post or not post['slug']:
            # Generate slug from URL or title
            if post.get('url'):
                url_parts = post['url'].split('/')
                post['slug'] = url_parts[-1] if url_parts else ""
            else:
                post['slug'] = self._generate_slug(post.get('title', ''))
            self.validation_stats['fixes_applied'] += 1
        
        # Validate ID
        if 'id' not in post or not post['id']:
            post['id'] = self._generate_id(post.get('url', ''), index)
            self.validation_stats['fixes_applied'] += 1
        
        return post
    
    def _validate_images(self, images: List[Dict[str, Any]], index: int, issues: List[str]) -> List[Dict[str, Any]]:
        """Validate and clean image data."""
        if not isinstance(images, list):
            issues.append("Images field is not a list")
            return []
        
        validated_images = []
        
        for i, image in enumerate(images):
            if not isinstance(image, dict):
                issues.append(f"Image {i} is not a dictionary")
                continue
            
            # Validate required image fields
            if 'original_url' not in image or not image['original_url']:
                issues.append(f"Image {i} missing URL")
                continue
            
            # Clean image data
            cleaned_image = {
                'original_url': image['original_url'].strip(),
                'alt_text': str(image.get('alt_text', '')).strip(),
                'title': str(image.get('title', '')).strip(),
                'caption': str(image.get('caption', '')).strip(),
                'width': image.get('width'),
                'height': image.get('height')
            }
            
            # Validate dimensions
            for dim in ['width', 'height']:
                if cleaned_image[dim]:
                    try:
                        if isinstance(cleaned_image[dim], str):
                            cleaned_image[dim] = int(cleaned_image[dim])
                    except ValueError:
                        cleaned_image[dim] = None
            
            validated_images.append(cleaned_image)
        
        return validated_images
    
    def _validate_links(self, links: List[Dict[str, Any]], index: int, issues: List[str]) -> List[Dict[str, Any]]:
        """Validate and clean link data."""
        if not isinstance(links, list):
            issues.append("Links field is not a list")
            return []
        
        validated_links = []
        seen_urls = set()
        
        for i, link in enumerate(links):
            if not isinstance(link, dict):
                issues.append(f"Link {i} is not a dictionary")
                continue
            
            if 'url' not in link or not link['url']:
                issues.append(f"Link {i} missing URL")
                continue
            
            url = link['url'].strip()
            
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Clean link data
            cleaned_link = {
                'url': url,
                'text': str(link.get('text', '')).strip(),
                'title': str(link.get('title', '')).strip(),
                'type': link.get('type', 'unknown')
            }
            
            # Validate link type
            if cleaned_link['type'] not in ['internal', 'external', 'email', 'phone']:
                cleaned_link['type'] = self._classify_link(url)
                self.validation_stats['fixes_applied'] += 1
            
            validated_links.append(cleaned_link)
        
        return validated_links
    
    def _validate_taxonomy(self, post: Dict[str, Any], index: int, issues: List[str]) -> Dict[str, Any]:
        """Validate and clean taxonomy fields (categories, tags)."""
        for field in ['categories', 'tags']:
            if field in post:
                if not isinstance(post[field], list):
                    issues.append(f"{field} is not a list")
                    post[field] = []
                    self.validation_stats['fixes_applied'] += 1
                else:
                    # Clean taxonomy items
                    cleaned_items = []
                    for item in post[field]:
                        if isinstance(item, str) and item.strip():
                            cleaned_items.append(item.strip())
                    
                    # Remove duplicates while preserving order
                    seen = set()
                    post[field] = [item for item in cleaned_items if not (item in seen or seen.add(item))]
            else:
                post[field] = []
        
        return post
    
    def _extract_date_from_url(self, url: str) -> Optional[datetime]:
        """Extract date from URL pattern."""
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            if len(path_parts) >= 4:
                year_str, month_str, day_str = path_parts[1:4]
                
                if (year_str.isdigit() and len(year_str) == 4 and
                    month_str.isdigit() and 1 <= int(month_str) <= 12 and
                    day_str.isdigit() and 1 <= int(day_str) <= 31):
                    
                    return datetime(int(year_str), int(month_str), int(day_str))
        except:
            pass
        
        return None
    
    def _generate_slug(self, title: str) -> str:
        """Generate a slug from title."""
        if not title:
            return "untitled"
        
        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special characters
        slug = re.sub(r'\s+', '-', slug)  # Replace spaces with hyphens
        slug = re.sub(r'-+', '-', slug)  # Remove multiple consecutive hyphens
        slug = slug.strip('-')  # Remove leading/trailing hyphens
        
        return slug or "untitled"
    
    def _generate_id(self, url: str, index: int) -> str:
        """Generate an ID for the post."""
        if url:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            if len(path_parts) >= 4:
                # For URLs like /libedge/2019/10/26/post-title
                return f"{path_parts[1]}-{path_parts[2]}-{path_parts[3]}-{path_parts[4]}"
        
        return f"post-{index}"
    
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
    
    def _generate_validation_report(self) -> Dict[str, Any]:
        """Generate a comprehensive validation report."""
        return {
            'statistics': self.validation_stats.copy(),
            'success_rate': (self.validation_stats['valid_posts'] / self.validation_stats['total_posts']) * 100 if self.validation_stats['total_posts'] > 0 else 0,
            'issues': self.issues.copy(),
            'summary': {
                'total_posts_processed': self.validation_stats['total_posts'],
                'posts_passed_validation': self.validation_stats['valid_posts'],
                'posts_with_issues': self.validation_stats['warnings'],
                'posts_failed_completely': self.validation_stats['errors'],
                'total_issues_found': self.validation_stats['issues_found'],
                'automatic_fixes_applied': self.validation_stats['fixes_applied']
            }
        }
    
    def save_validation_report(self, report: Dict[str, Any], output_path: str) -> None:
        """Save validation report to file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Validation report saved to: {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save validation report: {e}")
    
    def get_validation_summary(self) -> str:
        """Get a human-readable validation summary."""
        stats = self.validation_stats
        
        summary = f"""
Validation Summary:
==================
Total Posts Processed: {stats['total_posts']}
Posts Passed Validation: {stats['valid_posts']}
Posts with Issues: {stats['warnings']}
Posts Failed Completely: {stats['errors']}
Success Rate: {(stats['valid_posts'] / stats['total_posts']) * 100:.1f}% if stats['total_posts'] > 0 else 0
Total Issues Found: {stats['issues_found']}
Automatic Fixes Applied: {stats['fixes_applied']}
"""
        
        return summary.strip()