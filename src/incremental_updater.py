"""Incremental updater for detecting and updating changed blog posts."""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dateutil import parser as date_parser

from .config import ArchiveConfig
from .url_discovery import URLDiscovery
from .content_extractor import ContentExtractor
from .data_validator import DataValidator
from .json_generator import JSONGenerator
from .markdown_generator import MarkdownGenerator
from .image_downloader import ImageDownloader


class IncrementalUpdater:
    """Handles incremental updates to detect and archive new or changed posts."""
    
    def __init__(self, config: ArchiveConfig, output_dir: Path):
        self.config = config
        self.output_dir = Path(output_dir)
        self.logger = logging.getLogger("squarespace_archiver.incremental")
        
        # Initialize components
        self.url_discovery = URLDiscovery(config)
        self.content_extractor = ContentExtractor(config)
        self.data_validator = DataValidator(config)
        self.json_generator = JSONGenerator(config)
        self.markdown_generator = MarkdownGenerator(config)
        self.image_downloader = ImageDownloader(config)
        
        # Load existing archive data
        self.archive_data = self._load_existing_archive()
        self.existing_posts = self._build_post_index()
    
    def _load_existing_archive(self) -> Optional[Dict[str, Any]]:
        """Load existing archive data if available."""
        archive_file = self.output_dir / "archive.json"
        
        if not archive_file.exists():
            self.logger.info("No existing archive found")
            return None
        
        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.info(f"Loaded existing archive with {len(data.get('posts', []))} posts")
            return data
            
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to load existing archive: {e}")
            return None
    
    def _build_post_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index of existing posts for comparison."""
        if not self.archive_data:
            return {}
        
        index = {}
        for post in self.archive_data.get('posts', []):
            url = post.get('url', '')
            if url:
                index[url] = {
                    'id': post.get('id', ''),
                    'title': post.get('title', ''),
                    'published_date': post.get('published_date', ''),
                    'modified_date': post.get('modified_date', ''),
                    'content_hash': self._calculate_content_hash(post),
                    'post_data': post
                }
        
        return index
    
    def _calculate_content_hash(self, post: Dict[str, Any]) -> str:
        """Calculate hash of post content for change detection."""
        # Use key content fields for hash calculation
        content_fields = [
            post.get('title', ''),
            post.get('content', {}).get('html', ''),
            post.get('excerpt', ''),
            str(post.get('metadata', {}).get('categories', [])),
            str(post.get('metadata', {}).get('tags', []))
        ]
        
        content_string = '|'.join(content_fields)
        return hashlib.sha256(content_string.encode('utf-8')).hexdigest()
    
    async def check_for_updates(self, since_date: Optional[str] = None) -> Dict[str, Any]:
        """Check for new or updated posts."""
        self.logger.info("Checking for updates...")
        
        # Discover current URLs
        discovery_results = await self.url_discovery.discover_all_blog_urls()
        current_urls = set(discovery_results.get('all_urls', []))
        existing_urls = set(self.existing_posts.keys())
        
        # Find new URLs
        new_urls = current_urls - existing_urls
        
        # Check existing URLs for changes
        changed_urls = []
        unchanged_urls = []
        
        since_datetime = None
        if since_date:
            try:
                since_datetime = date_parser.parse(since_date)
                self.logger.info(f"Checking for changes since: {since_datetime}")
            except ValueError:
                self.logger.warning(f"Invalid date format: {since_date}, ignoring")
        
        for url in existing_urls & current_urls:  # URLs that exist in both
            if await self._has_post_changed(url, since_datetime):
                changed_urls.append(url)
            else:
                unchanged_urls.append(url)
        
        # URLs that were removed
        removed_urls = existing_urls - current_urls
        
        self.logger.info(f"Update check results:")
        self.logger.info(f"  New posts: {len(new_urls)}")
        self.logger.info(f"  Changed posts: {len(changed_urls)}")
        self.logger.info(f"  Unchanged posts: {len(unchanged_urls)}")
        self.logger.info(f"  Removed posts: {len(removed_urls)}")
        
        return {
            'new_urls': list(new_urls),
            'changed_urls': changed_urls,
            'unchanged_urls': unchanged_urls,
            'removed_urls': list(removed_urls),
            'new_posts': len(new_urls),
            'changed_posts': len(changed_urls),
            'total_current_posts': len(current_urls)
        }
    
    async def _has_post_changed(self, url: str, since_datetime: Optional[datetime] = None) -> bool:
        """Check if a post has changed since last archive."""
        if url not in self.existing_posts:
            return True  # New post
        
        existing_post = self.existing_posts[url]
        
        # Quick check: if we have a since_datetime, check modified date first
        if since_datetime:
            modified_date_str = existing_post.get('modified_date')
            if modified_date_str:
                try:
                    modified_date = date_parser.parse(modified_date_str)
                    if modified_date < since_datetime:
                        return False  # Not modified since the given date
                except ValueError:
                    pass  # Continue with content check if date parsing fails
        
        # Extract current content for comparison
        try:
            current_post_list = await self.content_extractor.extract_posts_from_urls([url])
            current_post = current_post_list[0] if current_post_list else None
            if not current_post:
                self.logger.warning(f"Could not extract content from {url}")
                return False
            
            current_hash = self._calculate_content_hash(current_post)
            existing_hash = existing_post['content_hash']
            
            return current_hash != existing_hash
            
        except Exception as e:
            self.logger.error(f"Error checking changes for {url}: {e}")
            return False
    
    async def update_archive(self, urls_to_update: Optional[List[str]] = None) -> Dict[str, Any]:
        """Update the archive with new or changed posts."""
        if urls_to_update is None:
            # Get all URLs that need updating
            update_check = await self.check_for_updates()
            urls_to_update = update_check['new_urls'] + update_check['changed_urls']
        
        if not urls_to_update:
            return {'updated_posts': 0, 'message': 'No posts to update'}
        
        self.logger.info(f"Updating archive with {len(urls_to_update)} posts...")
        
        # Extract content for all URLs to update
        updated_posts = []
        successful_updates = 0
        
        for i, url in enumerate(urls_to_update):
            self.logger.info(f"Processing update {i+1}/{len(urls_to_update)}: {url}")
            
            try:
                # Extract content
                post_data_list = await self.content_extractor.extract_posts_from_urls([url])
                post_data = post_data_list[0] if post_data_list else None
                
                if not post_data:
                    self.logger.warning(f"No content extracted for {url}")
                    continue
                
                # Validate content (using batch validator for single post)
                validated_posts, validation_summary = self.data_validator.validate_and_clean_posts([post_data])
                if validated_posts:
                    post_data = validated_posts[0]
                    post_data['validation'] = validation_summary
                else:
                    self.logger.warning(f"Validation failed for {url}")
                
                updated_posts.append(post_data)
                successful_updates += 1
                
                # Respectful delay
                await asyncio.sleep(self.config.rate_limit_delay)
                
            except Exception as e:
                self.logger.error(f"Failed to update {url}: {e}")
                continue
        
        if not updated_posts:
            return {'updated_posts': 0, 'message': 'No posts successfully updated'}
        
        # Merge with existing archive
        merged_archive_data = self._merge_with_existing_archive(updated_posts)
        
        # Generate outputs
        self.logger.info("Generating updated outputs...")
        
        # Update JSON archive
        json_results = self.json_generator.generate_archive(
            merged_archive_data['posts'], 
            self.output_dir
        )
        
        # Update Markdown files (only for updated posts)
        markdown_results = self.markdown_generator.generate_markdown_files(
            updated_posts, 
            self.output_dir
        )
        
        # Download new images
        download_results = await self.image_downloader.download_all_images(
            updated_posts, 
            self.output_dir
        )
        
        # Save update metadata
        self._save_update_metadata(urls_to_update, successful_updates)
        
        self.logger.info(f"Archive update completed: {successful_updates} posts updated")
        
        return {
            'updated_posts': successful_updates,
            'total_posts_in_archive': len(merged_archive_data['posts']),
            'json_results': json_results,
            'markdown_results': markdown_results,
            'download_results': download_results
        }
    
    def _merge_with_existing_archive(self, updated_posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge updated posts with existing archive data."""
        if not self.archive_data:
            # No existing archive, create new one
            return {
                'posts': updated_posts,
                'site_metadata': self._generate_basic_site_metadata(updated_posts)
            }
        
        # Create URL-to-post mapping for updated posts
        updated_by_url = {post['url']: post for post in updated_posts}
        
        # Update existing posts or add new ones
        merged_posts = []
        
        # First, process existing posts
        for existing_post in self.archive_data.get('posts', []):
            url = existing_post.get('url', '')
            
            if url in updated_by_url:
                # Use updated version
                merged_posts.append(updated_by_url[url])
                del updated_by_url[url]  # Remove from pending updates
            else:
                # Keep existing version
                merged_posts.append(existing_post)
        
        # Add any remaining new posts
        merged_posts.extend(updated_by_url.values())
        
        # Sort by published date
        merged_posts.sort(key=lambda x: x.get('published_date', ''), reverse=True)
        
        # Update site metadata
        updated_archive_data = self.archive_data.copy()
        updated_archive_data['posts'] = merged_posts
        
        # Update site metadata
        if 'site_metadata' in updated_archive_data:
            updated_archive_data['site_metadata']['total_posts'] = len(merged_posts)
            updated_archive_data['site_metadata']['last_updated'] = datetime.now().isoformat()
        
        return updated_archive_data
    
    def _generate_basic_site_metadata(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate basic site metadata for new archives."""
        return {
            'title': 'The Librarian Edge',
            'url': self.config.site_url,
            'total_posts': len(posts),
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
    
    def _save_update_metadata(self, updated_urls: List[str], successful_updates: int):
        """Save metadata about the update operation."""
        update_metadata = {
            'timestamp': datetime.now().isoformat(),
            'updated_urls': updated_urls,
            'successful_updates': successful_updates,
            'total_requested_updates': len(updated_urls)
        }
        
        # Save to incremental updates log
        updates_log_file = self.output_dir / "incremental_updates.json"
        
        if updates_log_file.exists():
            try:
                with open(updates_log_file, 'r', encoding='utf-8') as f:
                    existing_log = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing_log = {'updates': []}
        else:
            existing_log = {'updates': []}
        
        existing_log['updates'].append(update_metadata)
        
        # Keep only last 50 update records
        existing_log['updates'] = existing_log['updates'][-50:]
        
        with open(updates_log_file, 'w', encoding='utf-8') as f:
            json.dump(existing_log, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Update metadata saved to {updates_log_file}")
    
    def get_update_history(self) -> List[Dict[str, Any]]:
        """Get history of incremental updates."""
        updates_log_file = self.output_dir / "incremental_updates.json"
        
        if not updates_log_file.exists():
            return []
        
        try:
            with open(updates_log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            return log_data.get('updates', [])
            
        except (json.JSONDecodeError, IOError):
            return []
    
    async def find_orphaned_posts(self) -> List[str]:
        """Find posts in archive that no longer exist on the site."""
        if not self.archive_data:
            return []
        
        # Discover current URLs
        discovery_results = await self.url_discovery.discover_all_blog_urls()
        current_urls = set(discovery_results.get('all_urls', []))
        
        # Find archived URLs that no longer exist
        archived_urls = set(post.get('url', '') for post in self.archive_data.get('posts', []))
        orphaned_urls = archived_urls - current_urls
        
        return list(orphaned_urls)