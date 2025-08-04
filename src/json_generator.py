"""JSON archive generator for blog posts."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import shutil

from .config import ArchiveConfig


class JSONGenerator:
    """Generates structured JSON archives from extracted blog posts."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.json_generator")
    
    def generate_archive(self, posts: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Any]:
        """Generate complete JSON archive from extracted posts."""
        self.logger.info(f"Generating JSON archive for {len(posts)} posts...")
        
        # Create output directory
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate site-level metadata
        site_metadata = self._generate_site_metadata(posts)
        
        # Process posts for archive
        processed_posts = self._process_posts_for_archive(posts)
        
        # Create complete archive structure
        archive = {
            "site_metadata": site_metadata,
            "posts": processed_posts,
            "assets": {
                "images": self._collect_image_references(posts),
                "css": [],  # Will be populated when CSS is preserved
                "js": []    # Will be populated if JS files are needed
            },
            "archive_metadata": {
                "generated_at": datetime.now().isoformat(),
                "generator": "Squarespace Blog Archiver v0.1.0",
                "total_posts": len(posts),
                "extraction_summary": self._generate_extraction_summary(posts)
            }
        }
        
        # Save main archive
        archive_file = output_dir / "archive.json"
        self._save_json_file(archive, archive_file, pretty=True)
        
        # Save timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = output_dir / f"archive_backup_{timestamp}.json"
        self._save_json_file(archive, backup_file, pretty=True)
        
        # Save individual post files for easier access
        posts_dir = output_dir / "posts"
        posts_dir.mkdir(exist_ok=True)
        
        for post in processed_posts:
            post_file = posts_dir / f"{post['id']}.json"
            self._save_json_file(post, post_file, pretty=True)
        
        # Generate index files
        self._generate_index_files(archive, output_dir)
        
        self.logger.info(f"JSON archive generated successfully:")
        self.logger.info(f"  Main archive: {archive_file}")
        self.logger.info(f"  Backup: {backup_file}")
        self.logger.info(f"  Individual posts: {len(processed_posts)} files in {posts_dir}")
        
        return {
            "main_archive": str(archive_file),
            "backup_archive": str(backup_file),
            "posts_directory": str(posts_dir),
            "total_posts": len(processed_posts),
            "archive_size": self._get_file_size(archive_file)
        }
    
    def _generate_site_metadata(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate site-level metadata."""
        if not posts:
            return {
                "title": "Blog Archive",
                "url": self.config.site_url,
                "scraped_date": datetime.now().isoformat(),
                "total_posts": 0
            }
        
        # Extract dates for timeline
        dates = []
        for post in posts:
            if post.get('published_date'):
                try:
                    dates.append(post['published_date'])
                except:
                    pass
        
        dates.sort()
        
        # Generate metadata
        metadata = {
            "title": "The Librarian Edge - Blog Archive",
            "url": self.config.site_url,
            "scraped_date": datetime.now().isoformat(),
            "total_posts": len(posts),
            "date_range": {
                "earliest_post": dates[0] if dates else None,
                "latest_post": dates[-1] if dates else None
            },
            "content_statistics": {
                "total_words": sum(post.get('word_count', 0) for post in posts),
                "total_images": sum(len(post.get('images', [])) for post in posts),
                "total_links": sum(len(post.get('links', [])) for post in posts),
                "average_words_per_post": sum(post.get('word_count', 0) for post in posts) // len(posts) if posts else 0
            },
            "authors": list(set(post.get('author', '') for post in posts if post.get('author'))),
            "categories": list(set(cat for post in posts for cat in post.get('categories', []))),
            "tags": list(set(tag for post in posts for tag in post.get('tags', [])))
        }
        
        return metadata
    
    def _process_posts_for_archive(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process posts for inclusion in archive."""
        processed_posts = []
        
        for post in posts:
            # Create clean copy for archive
            archived_post = {
                "id": post.get('id', ''),
                "title": post.get('title', ''),
                "slug": post.get('slug', ''),
                "url": post.get('url', ''),
                "published_date": post.get('published_date', ''),
                "modified_date": post.get('modified_date', ''),
                "author": post.get('author', ''),
                "excerpt": post.get('excerpt', ''),
                "content": {
                    "html": post.get('content_html', ''),
                    "text": post.get('content_text', ''),
                    "markdown": post.get('content_markdown', ''),
                    "word_count": post.get('word_count', 0)
                },
                "metadata": {
                    "categories": post.get('categories', []),
                    "tags": post.get('tags', []),
                    "meta_description": post.get('meta_description', '')
                },
                "assets": {
                    "images": self._process_images_for_archive(post.get('images', [])),
                    "links": self._process_links_for_archive(post.get('links', []))
                },
                "archive_info": {
                    "scraped_at": post.get('scraped_at', ''),
                    "extracted_at": post.get('extracted_at', ''),
                    "validation_info": post.get('validation', {})
                }
            }
            
            processed_posts.append(archived_post)
        
        # Sort by published date
        processed_posts.sort(key=lambda x: x.get('published_date', ''), reverse=True)
        
        return processed_posts
    
    def _process_images_for_archive(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process images for archive format."""
        processed_images = []
        
        for img in images:
            processed_img = {
                "original_url": img.get('original_url', ''),
                "local_path": "",  # Will be populated when images are downloaded
                "alt_text": img.get('alt_text', ''),
                "caption": img.get('caption', ''),
                "title": img.get('title', ''),
                "dimensions": {
                    "width": img.get('width'),
                    "height": img.get('height')
                }
            }
            processed_images.append(processed_img)
        
        return processed_images
    
    def _process_links_for_archive(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process links for archive format."""
        # Group links by type
        link_groups = {
            "internal": [],
            "external": [],
            "email": [],
            "phone": []
        }
        
        for link in links:
            link_type = link.get('type', 'unknown')
            processed_link = {
                "url": link.get('url', ''),
                "text": link.get('text', ''),
                "title": link.get('title', '')
            }
            
            if link_type in link_groups:
                link_groups[link_type].append(processed_link)
            else:
                link_groups['external'].append(processed_link)
        
        return link_groups
    
    def _collect_image_references(self, posts: List[Dict[str, Any]]) -> List[str]:
        """Collect all unique image URLs from posts."""
        image_urls = set()
        
        for post in posts:
            for img in post.get('images', []):
                if img.get('original_url'):
                    image_urls.add(img['original_url'])
        
        return sorted(list(image_urls))
    
    def _generate_extraction_summary(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of extraction process."""
        if not posts:
            return {}
        
        # Count validation issues
        total_issues = 0
        total_fixes = 0
        
        for post in posts:
            validation = post.get('validation', {})
            total_issues += validation.get('issues_found', 0)
            # Count fixes from validation report if available
        
        # Content statistics
        posts_with_images = sum(1 for post in posts if post.get('images'))
        posts_with_links = sum(1 for post in posts if post.get('links'))
        posts_with_categories = sum(1 for post in posts if post.get('categories'))
        posts_with_tags = sum(1 for post in posts if post.get('tags'))
        
        return {
            "extraction_success_rate": "100%",  # All posts in this list were successfully extracted
            "content_completeness": {
                "posts_with_images": posts_with_images,
                "posts_with_links": posts_with_links,
                "posts_with_categories": posts_with_categories,
                "posts_with_tags": posts_with_tags
            },
            "data_quality": {
                "validation_issues_found": total_issues,
                "automatic_fixes_applied": total_fixes
            }
        }
    
    def _generate_index_files(self, archive: Dict[str, Any], output_dir: Path) -> None:
        """Generate useful index files for the archive."""
        
        # Generate posts index (list of all posts with basic info)
        posts_index = []
        for post in archive['posts']:
            posts_index.append({
                "id": post.get('id'),
                "title": post.get('title'),
                "date": post.get('published_date'),
                "author": post.get('author'),
                "word_count": post.get('content', {}).get('word_count', 0),
                "url": post.get('url'),
                "file": f"posts/{post.get('id')}.json"
            })
        
        self._save_json_file(posts_index, output_dir / "posts_index.json", pretty=True)
        
        # Generate timeline index (posts organized by year/month)
        timeline = {}
        for post in archive['posts']:
            date_str = post.get('published_date', '')
            if date_str:
                try:
                    date_parts = date_str[:7]  # YYYY-MM
                    year = date_str[:4]
                    
                    if year not in timeline:
                        timeline[year] = {}
                    
                    if date_parts not in timeline[year]:
                        timeline[year][date_parts] = []
                    
                    timeline[year][date_parts].append({
                        "id": post.get('id'),
                        "title": post.get('title'),
                        "date": post.get('published_date')
                    })
                except:
                    pass
        
        self._save_json_file(timeline, output_dir / "timeline_index.json", pretty=True)
        
        # Generate categories index
        categories_index = {}
        for post in archive['posts']:
            for category in post.get('metadata', {}).get('categories', []):
                if category not in categories_index:
                    categories_index[category] = []
                
                categories_index[category].append({
                    "id": post.get('id'),
                    "title": post.get('title'),
                    "date": post.get('published_date')
                })
        
        self._save_json_file(categories_index, output_dir / "categories_index.json", pretty=True)
        
        # Generate tags index
        tags_index = {}
        for post in archive['posts']:
            for tag in post.get('metadata', {}).get('tags', []):
                if tag not in tags_index:
                    tags_index[tag] = []
                
                tags_index[tag].append({
                    "id": post.get('id'),
                    "title": post.get('title'),
                    "date": post.get('published_date')
                })
        
        self._save_json_file(tags_index, output_dir / "tags_index.json", pretty=True)
        
        self.logger.info("Generated index files: posts_index.json, timeline_index.json, categories_index.json, tags_index.json")
    
    def _save_json_file(self, data: Any, file_path: Path, pretty: bool = True) -> None:
        """Save data to JSON file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
                else:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            
            self.logger.debug(f"Saved JSON file: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON file {file_path}: {e}")
            raise
    
    def _get_file_size(self, file_path: Path) -> str:
        """Get human-readable file size."""
        try:
            size = file_path.stat().st_size
            
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            
            return f"{size:.1f} TB"
            
        except:
            return "Unknown"
    
    def validate_archive(self, archive_file: Path) -> Dict[str, Any]:
        """Validate the generated JSON archive."""
        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                archive = json.load(f)
            
            validation_results = {
                "valid": True,
                "issues": [],
                "statistics": {}
            }
            
            # Check required top-level keys
            required_keys = ['site_metadata', 'posts', 'assets', 'archive_metadata']
            for key in required_keys:
                if key not in archive:
                    validation_results["issues"].append(f"Missing required key: {key}")
                    validation_results["valid"] = False
            
            # Validate posts
            if 'posts' in archive:
                posts = archive['posts']
                validation_results["statistics"]["total_posts"] = len(posts)
                
                posts_with_content = 0
                posts_with_dates = 0
                
                for i, post in enumerate(posts):
                    # Check required post fields
                    if not post.get('id'):
                        validation_results["issues"].append(f"Post {i}: Missing ID")
                    
                    if not post.get('title'):
                        validation_results["issues"].append(f"Post {i}: Missing title")
                    
                    if post.get('content', {}).get('text'):
                        posts_with_content += 1
                    
                    if post.get('published_date'):
                        posts_with_dates += 1
                
                validation_results["statistics"]["posts_with_content"] = posts_with_content
                validation_results["statistics"]["posts_with_dates"] = posts_with_dates
                validation_results["statistics"]["content_completeness"] = (posts_with_content / len(posts)) * 100 if posts else 0
            
            if validation_results["issues"]:
                validation_results["valid"] = False
            
            return validation_results
            
        except Exception as e:
            return {
                "valid": False,
                "issues": [f"Failed to validate archive: {e}"],
                "statistics": {}
            }