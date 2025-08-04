"""Image downloader and organizer for blog archives."""

import asyncio
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin
import aiohttp
import aiofiles
from PIL import Image, ImageOps
import io

from .config import ArchiveConfig
from .logger import ProgressLogger


class ImageDownloader:
    """Downloads and organizes images for blog archives."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.image_downloader")
        
        # Track downloaded images to avoid duplicates
        self.downloaded_images: Dict[str, str] = {}  # URL -> local_path
        self.failed_downloads: Set[str] = set()
        
        # Statistics
        self.stats = {
            'total_images': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'duplicate_skips': 0,
            'total_size': 0
        }
    
    async def download_all_images(self, posts: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Any]:
        """Download all images from all posts."""
        self.logger.info("Starting image download process...")
        
        # Create images directory
        images_dir = Path(output_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # Collect all unique image URLs
        image_urls = self._collect_unique_image_urls(posts)
        self.stats['total_images'] = len(image_urls)
        
        self.logger.info(f"Found {len(image_urls)} unique images to download")
        
        if not image_urls:
            return self._generate_download_report(images_dir)
        
        # Download images with progress tracking
        progress = ProgressLogger(self.logger, len(image_urls), "Downloading images")
        
        # Use semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent downloads
        
        async with aiohttp.ClientSession(
            headers={'User-Agent': self.config.scraping.user_agent},
            timeout=aiohttp.ClientTimeout(total=60)
        ) as session:
            
            tasks = []
            for url in image_urls:
                task = self._download_single_image(session, semaphore, url, images_dir, progress)
                tasks.append(task)
            
            # Execute downloads with proper error handling
            await asyncio.gather(*tasks, return_exceptions=True)
        
        progress.complete()
        
        # Update posts with local image paths
        updated_posts = self._update_posts_with_local_paths(posts)
        
        # Generate download report
        report = self._generate_download_report(images_dir)
        
        self.logger.info(f"Image download complete:")
        self.logger.info(f"  Successfully downloaded: {self.stats['successful_downloads']} images")
        self.logger.info(f"  Failed downloads: {self.stats['failed_downloads']} images")
        self.logger.info(f"  Total size: {self._format_size(self.stats['total_size'])}")
        
        return {
            'updated_posts': updated_posts,
            'download_report': report
        }
    
    async def _download_single_image(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, 
                                   url: str, images_dir: Path, progress: ProgressLogger) -> None:
        """Download a single image with error handling."""
        
        async with semaphore:
            try:
                # Check if already downloaded
                if url in self.downloaded_images:
                    self.stats['duplicate_skips'] += 1
                    progress.update()
                    return
                
                # Check if previously failed
                if url in self.failed_downloads:
                    progress.update()
                    return
                
                # Generate local filename
                local_filename = self._generate_local_filename(url)
                local_path = images_dir / local_filename
                
                # Skip if file already exists
                if local_path.exists():
                    self.downloaded_images[url] = str(local_path.relative_to(images_dir))
                    self.stats['duplicate_skips'] += 1
                    progress.update()
                    return
                
                # Download image
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Validate image content
                        if self._is_valid_image(content):
                            # Process image if needed
                            processed_content = await self._process_image(content, url)
                            
                            # Save to file
                            async with aiofiles.open(local_path, 'wb') as f:
                                await f.write(processed_content)
                            
                            # Update tracking
                            self.downloaded_images[url] = str(local_path.relative_to(images_dir))
                            self.stats['successful_downloads'] += 1
                            self.stats['total_size'] += len(processed_content)
                            
                            self.logger.debug(f"Downloaded: {url} -> {local_filename}")
                            
                        else:
                            self.logger.warning(f"Invalid image content: {url}")
                            self.failed_downloads.add(url)
                            self.stats['failed_downloads'] += 1
                    
                    else:
                        self.logger.warning(f"Failed to download {url}: HTTP {response.status}")
                        self.failed_downloads.add(url)
                        self.stats['failed_downloads'] += 1
                
                # Add delay to be respectful
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Error downloading {url}: {e}")
                self.failed_downloads.add(url)
                self.stats['failed_downloads'] += 1
            
            finally:
                progress.update()
    
    def _collect_unique_image_urls(self, posts: List[Dict[str, Any]]) -> List[str]:
        """Collect all unique image URLs from posts."""
        unique_urls = set()
        
        for post in posts:
            images = post.get('images', [])
            for img in images:
                url = img.get('original_url', '')
                if url and url.startswith('http'):
                    unique_urls.add(url)
        
        return sorted(list(unique_urls))
    
    def _generate_local_filename(self, url: str) -> str:
        """Generate a local filename for an image URL."""
        
        # Parse URL
        parsed = urlparse(url)
        path = parsed.path
        
        # Extract filename and extension
        if path:
            original_filename = Path(path).name
            if original_filename and '.' in original_filename:
                name, ext = original_filename.rsplit('.', 1)
                ext = ext.lower()
                
                # Validate extension
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                    # Create hash-based filename to avoid conflicts
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                    safe_name = self._sanitize_filename(name)
                    
                    if safe_name:
                        return f"{safe_name}_{url_hash}.{ext}"
                    else:
                        return f"image_{url_hash}.{ext}"
        
        # Fallback: use URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return f"image_{url_hash}.jpg"  # Default to jpg
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be filesystem-safe."""
        
        # Remove or replace problematic characters
        import re
        
        # Replace spaces and special chars with underscores
        sanitized = re.sub(r'[^\w\-.]', '_', filename)
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        return sanitized
    
    def _is_valid_image(self, content: bytes) -> bool:
        """Check if content is a valid image."""
        
        if len(content) < 100:  # Too small to be a real image
            return False
        
        # Check magic bytes for common image formats
        if content.startswith(b'\xff\xd8\xff'):  # JPEG
            return True
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
            return True
        elif content.startswith(b'GIF8'):  # GIF
            return True
        elif content.startswith(b'RIFF') and b'WEBP' in content[:20]:  # WebP
            return True
        elif content.startswith(b'<svg') or b'<svg' in content[:100]:  # SVG
            return True
        
        # Try to open with PIL as fallback
        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
            return True
        except:
            return False
    
    async def _process_image(self, content: bytes, url: str) -> bytes:
        """Process image if needed (resize, optimize, etc.)."""
        
        # For now, just return original content
        # In the future, we could add:
        # - Resizing large images
        # - Converting formats
        # - Optimizing file sizes
        
        try:
            # Check if image is too large and needs resizing
            with Image.open(io.BytesIO(content)) as img:
                width, height = img.size
                max_width = self.config.output.max_image_width
                
                if width > max_width:
                    # Resize image
                    ratio = max_width / width
                    new_height = int(height * ratio)
                    
                    resized_img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Save to bytes
                    output = io.BytesIO()
                    
                    # Determine format
                    format = img.format or 'JPEG'
                    if format.upper() == 'JPEG':
                        resized_img.save(output, format=format, quality=self.config.output.image_quality, optimize=True)
                    else:
                        resized_img.save(output, format=format, optimize=True)
                    
                    return output.getvalue()
        
        except Exception as e:
            self.logger.debug(f"Image processing failed for {url}: {e}")
        
        # Return original content if processing fails
        return content
    
    def _update_posts_with_local_paths(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update posts with local image paths."""
        
        updated_posts = []
        
        for post in posts:
            updated_post = post.copy()
            updated_images = []
            
            for img in post.get('images', []):
                updated_img = img.copy()
                original_url = img.get('original_url', '')
                
                if original_url in self.downloaded_images:
                    updated_img['local_path'] = self.downloaded_images[original_url]
                    updated_img['download_status'] = 'success'
                elif original_url in self.failed_downloads:
                    updated_img['local_path'] = ''
                    updated_img['download_status'] = 'failed'
                else:
                    updated_img['local_path'] = ''
                    updated_img['download_status'] = 'skipped'
                
                updated_images.append(updated_img)
            
            updated_post['images'] = updated_images
            updated_posts.append(updated_post)
        
        return updated_posts
    
    def _generate_download_report(self, images_dir: Path) -> Dict[str, Any]:
        """Generate a comprehensive download report."""
        
        report = {
            'summary': {
                'total_images_found': self.stats['total_images'],
                'successful_downloads': self.stats['successful_downloads'],
                'failed_downloads': self.stats['failed_downloads'],
                'duplicate_skips': self.stats['duplicate_skips'],
                'success_rate': (self.stats['successful_downloads'] / self.stats['total_images']) * 100 if self.stats['total_images'] > 0 else 0,
                'total_size': self.stats['total_size'],
                'total_size_formatted': self._format_size(self.stats['total_size'])
            },
            'directories': {
                'images_directory': str(images_dir),
                'total_files': len(list(images_dir.glob('*'))) if images_dir.exists() else 0
            },
            'downloaded_images': dict(self.downloaded_images),
            'failed_urls': list(self.failed_downloads),
            'generated_at': datetime.now().isoformat()
        }
        
        # Save report to file
        try:
            import json
            report_file = images_dir / 'download_report.json'
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            report['report_file'] = str(report_file)
            
        except Exception as e:
            self.logger.warning(f"Failed to save download report: {e}")
        
        return report
    
    def _format_size(self, size_bytes: int) -> str:
        """Format byte size in human-readable format."""
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.1f} TB"
    
    def optimize_images_directory(self, images_dir: Path) -> Dict[str, Any]:
        """Optimize all images in the directory (post-processing)."""
        
        self.logger.info(f"Optimizing images in {images_dir}...")
        
        if not images_dir.exists():
            return {'error': 'Images directory does not exist'}
        
        image_files = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.jpeg')) + list(images_dir.glob('*.png'))
        
        optimized_count = 0
        total_saved = 0
        
        for image_file in image_files:
            try:
                original_size = image_file.stat().st_size
                
                # Optimize with PIL
                with Image.open(image_file) as img:
                    # Convert RGBA to RGB for JPEG
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Save optimized
                    img.save(image_file, optimize=True, quality=self.config.output.image_quality)
                
                new_size = image_file.stat().st_size
                saved = original_size - new_size
                
                if saved > 0:
                    total_saved += saved
                    optimized_count += 1
                
            except Exception as e:
                self.logger.debug(f"Failed to optimize {image_file}: {e}")
        
        optimization_report = {
            'total_images': len(image_files),
            'optimized_images': optimized_count,
            'total_saved': total_saved,
            'total_saved_formatted': self._format_size(total_saved)
        }
        
        self.logger.info(f"Image optimization complete: {optimized_count} images optimized, {self._format_size(total_saved)} saved")
        
        return optimization_report