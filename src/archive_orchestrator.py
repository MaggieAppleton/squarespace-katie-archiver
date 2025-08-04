"""Archive orchestrator with resumable functionality and progress tracking."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import time

from .config import ArchiveConfig
from .connectivity import ConnectivityChecker
from .site_explorer import SiteExplorer
from .url_discovery import URLDiscovery
from .content_extractor import ContentExtractor
from .data_validator import DataValidator
from .json_generator import JSONGenerator
from .markdown_generator import MarkdownGenerator
from .image_downloader import ImageDownloader


class ArchiveState:
    """Manages the archive state for resumable operations."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load existing state or create new one."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # Corrupted state file, start fresh
                pass
        
        return {
            'session_id': self._generate_session_id(),
            'started_at': datetime.now().isoformat(),
            'phase': 'initialization',
            'total_posts': 0,
            'completed_urls': [],
            'failed_urls': [],
            'current_url': None,
            'progress': {
                'urls_discovered': 0,
                'posts_extracted': 0,
                'posts_validated': 0,
                'json_generated': False,
                'markdown_generated': False,
                'images_downloaded': 0
            },
            'statistics': {
                'start_time': time.time(),
                'extraction_times': [],
                'total_content_size': 0,
                'total_images_found': 0
            },
            'resume_data': {}
        }
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_part = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        return f"archive_{timestamp}_{random_part}"
    
    def save(self) -> None:
        """Save current state to file."""
        self.state['last_updated'] = datetime.now().isoformat()
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def update_phase(self, phase: str) -> None:
        """Update current phase."""
        self.state['phase'] = phase
        self.save()
    
    def mark_url_completed(self, url: str, post_data: Optional[Dict] = None) -> None:
        """Mark URL as completed."""
        if url not in self.state['completed_urls']:
            self.state['completed_urls'].append(url)
        
        if url in self.state['failed_urls']:
            self.state['failed_urls'].remove(url)
        
        if post_data:
            self.state['progress']['posts_extracted'] += 1
            self.state['statistics']['total_content_size'] += len(post_data.get('content_html', ''))
            self.state['statistics']['total_images_found'] += len(post_data.get('images', []))
        
        self.save()
    
    def mark_url_failed(self, url: str, error: str) -> None:
        """Mark URL as failed."""
        if url not in self.state['failed_urls']:
            self.state['failed_urls'].append(url)
        
        if 'errors' not in self.state:
            self.state['errors'] = {}
        self.state['errors'][url] = error
        
        self.save()
    
    def set_current_url(self, url: Optional[str]) -> None:
        """Set currently processing URL."""
        self.state['current_url'] = url
        self.save()
    
    def get_pending_urls(self, all_urls: List[str]) -> List[str]:
        """Get list of URLs that still need processing."""
        completed = set(self.state['completed_urls'])
        return [url for url in all_urls if url not in completed]
    
    def update_progress(self, **kwargs) -> None:
        """Update progress counters."""
        for key, value in kwargs.items():
            if key in self.state['progress']:
                self.state['progress'][key] = value
        self.save()
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get human-readable progress summary."""
        total_urls = self.state['total_posts']
        completed = len(self.state['completed_urls'])
        failed = len(self.state['failed_urls'])
        
        if total_urls > 0:
            completion_rate = (completed / total_urls) * 100
        else:
            completion_rate = 0
        
        elapsed_time = time.time() - self.state['statistics']['start_time']
        
        return {
            'session_id': self.state['session_id'],
            'phase': self.state['phase'],
            'completion_rate': completion_rate,
            'completed_urls': completed,
            'failed_urls': failed,
            'total_urls': total_urls,
            'current_url': self.state['current_url'],
            'elapsed_time': elapsed_time,
            'estimated_remaining': self._estimate_remaining_time(),
            'progress': self.state['progress'].copy()
        }
    
    def _estimate_remaining_time(self) -> float:
        """Estimate remaining time based on current progress."""
        extraction_times = self.state['statistics']['extraction_times']
        completed = len(self.state['completed_urls'])
        total = self.state['total_posts']
        
        if not extraction_times or completed == 0 or total == 0:
            return 0
        
        avg_time_per_post = sum(extraction_times) / len(extraction_times)
        remaining_posts = total - completed
        
        return remaining_posts * avg_time_per_post


class ArchiveOrchestrator:
    """Orchestrates the complete archiving process with resumable functionality."""
    
    def __init__(self, config: ArchiveConfig, output_dir: Path, state_file: Optional[Path] = None):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up state management
        if state_file is None:
            state_file = self.output_dir / "archive_state.json"
        
        self.state = ArchiveState(state_file)
        self.logger = logging.getLogger("squarespace_archiver.orchestrator")
        
        # Initialize components
        self.connectivity_checker = ConnectivityChecker(config)
        self.site_explorer = SiteExplorer(config)
        self.url_discovery = URLDiscovery(config)
        self.content_extractor = ContentExtractor(config)
        self.data_validator = DataValidator(config)
        self.json_generator = JSONGenerator(config)
        self.markdown_generator = MarkdownGenerator(config)
        self.image_downloader = ImageDownloader(config)
        
        # Progress tracking
        self.progress_callback = None
        self.last_progress_report = time.time()
    
    def set_progress_callback(self, callback):
        """Set callback function for progress updates."""
        self.progress_callback = callback
    
    async def archive_full(self, resume: bool = True) -> Dict[str, Any]:
        """Run complete archive process with resumable functionality."""
        try:
            self.logger.info(f"Starting archive session: {self.state.state['session_id']}")
            
            if resume and self.state.state['phase'] != 'initialization':
                self.logger.info(f"Resuming from phase: {self.state.state['phase']}")
            else:
                self.logger.info("Starting new archive session")
                self.state.update_phase('initialization')
            
            # Phase 1: Connectivity & Site Discovery
            if self.state.state['phase'] in ['initialization', 'discovery']:
                await self._phase_discovery()
            
            # Phase 2: Content Extraction
            if self.state.state['phase'] in ['discovery', 'extraction']:
                await self._phase_extraction()
            
            # Phase 3: Output Generation
            if self.state.state['phase'] in ['extraction', 'output_generation']:
                await self._phase_output_generation()
            
            # Mark completion
            self.state.update_phase('completed')
            self.logger.info("Archive process completed successfully")
            
            return {
                'success': True,
                'session_id': self.state.state['session_id'],
                'summary': self._generate_completion_summary()
            }
            
        except Exception as e:
            self.logger.error(f"Archive process failed: {e}")
            self.state.state['error'] = str(e)
            self.state.save()
            raise
    
    async def _phase_discovery(self):
        """Phase 1: Discover URLs and analyze site structure."""
        self.logger.info("Phase 1: Site Discovery & URL Collection")
        self.state.update_phase('discovery')
        
        # Check connectivity
        self.logger.info("Checking site connectivity...")
        basic_check = self.connectivity_checker.check_basic_connectivity()
        if not basic_check['success']:
            raise Exception(f"Site connectivity failed: {basic_check['error']}")
        
        js_check = await self.connectivity_checker.check_javascript_rendering()
        if not js_check['success']:
            raise Exception(f"JavaScript rendering failed: {js_check['error']}")
        
        # Discover URLs
        self.logger.info("Discovering blog post URLs...")
        discovery_results = await self.url_discovery.discover_all_blog_urls()
        
        all_urls = discovery_results.get('all_urls', [])
        if not all_urls:
            raise Exception("No blog post URLs found")
        
        self.state.state['total_posts'] = len(all_urls)
        self.state.state['all_urls'] = all_urls
        self.state.update_progress(urls_discovered=len(all_urls))
        
        self.logger.info(f"Discovered {len(all_urls)} blog post URLs")
        self._report_progress()
    
    async def _phase_extraction(self):
        """Phase 2: Extract content from all posts."""
        self.logger.info("Phase 2: Content Extraction")
        self.state.update_phase('extraction')
        
        all_urls = self.state.state.get('all_urls', [])
        pending_urls = self.state.get_pending_urls(all_urls)
        
        self.logger.info(f"Extracting content from {len(pending_urls)} remaining URLs...")
        
        extracted_posts = []
        
        for i, url in enumerate(pending_urls):
            self.state.set_current_url(url)
            start_time = time.time()
            
            try:
                self.logger.info(f"Processing {i+1}/{len(pending_urls)}: {url}")
                
                # Extract content
                post_data_list = await self.content_extractor.extract_posts_from_urls([url])
                post_data = post_data_list[0] if post_data_list else None
                
                if not post_data:
                    raise Exception("No content extracted")
                
                # Validate content (using batch validator for single post)
                validated_posts, validation_summary = self.data_validator.validate_and_clean_posts([post_data])
                if validated_posts:
                    post_data = validated_posts[0]
                    post_data['validation'] = validation_summary
                else:
                    self.logger.warning(f"Validation failed for {url}")
                
                extracted_posts.append(post_data)
                
                # Update progress
                extraction_time = time.time() - start_time
                self.state.state['statistics']['extraction_times'].append(extraction_time)
                self.state.mark_url_completed(url, post_data)
                
                self.logger.info(f"✅ Extracted in {extraction_time:.2f}s")
                
                # Respectful delay
                await asyncio.sleep(self.config.scraping.delay_between_requests)
                
            except Exception as e:
                self.logger.error(f"❌ Failed to extract {url}: {e}")
                self.state.mark_url_failed(url, str(e))
                continue
            
            # Progress reporting
            if time.time() - self.last_progress_report > 30:  # Every 30 seconds
                self._report_progress()
        
        # Save extracted data
        self.state.state['extracted_posts'] = extracted_posts
        self.state.update_progress(posts_extracted=len(extracted_posts))
        self.state.set_current_url(None)
        
        self.logger.info(f"Content extraction completed: {len(extracted_posts)} posts extracted")
    
    async def _phase_output_generation(self):
        """Phase 3: Generate all output formats."""
        self.logger.info("Phase 3: Output Generation")
        self.state.update_phase('output_generation')
        
        extracted_posts = self.state.state.get('extracted_posts', [])
        if not extracted_posts:
            raise Exception("No extracted posts available for output generation")
        
        # Generate JSON archive
        self.logger.info("Generating JSON archive...")
        json_results = self.json_generator.generate_archive(extracted_posts, self.output_dir)
        self.state.update_progress(json_generated=True)
        
        # Generate Markdown files
        self.logger.info("Generating Markdown files...")
        markdown_results = self.markdown_generator.generate_markdown_files(extracted_posts, self.output_dir)
        self.state.update_progress(markdown_generated=True)
        
        # Download images
        self.logger.info("Downloading images...")
        download_results = await self.image_downloader.download_all_images(extracted_posts, self.output_dir)
        images_downloaded = download_results['download_report']['summary']['successful_downloads']
        self.state.update_progress(images_downloaded=images_downloaded)
        
        # Store generation results
        self.state.state['output_results'] = {
            'json': json_results,
            'markdown': markdown_results,
            'images': download_results
        }
        
        self.logger.info("Output generation completed")
    
    def _report_progress(self):
        """Report current progress."""
        summary = self.state.get_progress_summary()
        
        self.logger.info("=" * 50)
        self.logger.info(f"PROGRESS REPORT - Session: {summary['session_id']}")
        self.logger.info("=" * 50)
        self.logger.info(f"Phase: {summary['phase']}")
        self.logger.info(f"Completion: {summary['completion_rate']:.1f}%")
        self.logger.info(f"Processed: {summary['completed_urls']}/{summary['total_urls']} URLs")
        self.logger.info(f"Failed: {summary['failed_urls']} URLs")
        self.logger.info(f"Elapsed time: {summary['elapsed_time']:.1f}s")
        
        if summary['estimated_remaining'] > 0:
            self.logger.info(f"Estimated remaining: {summary['estimated_remaining']:.1f}s")
        
        if summary['current_url']:
            self.logger.info(f"Current: {summary['current_url']}")
        
        self.logger.info("=" * 50)
        
        self.last_progress_report = time.time()
        
        # Call progress callback if set
        if self.progress_callback:
            self.progress_callback(summary)
    
    def _generate_completion_summary(self) -> Dict[str, Any]:
        """Generate final completion summary."""
        progress = self.state.get_progress_summary()
        
        return {
            'total_posts': progress['total_urls'],
            'successful_posts': progress['completed_urls'],
            'failed_posts': progress['failed_urls'],
            'success_rate': progress['completion_rate'],
            'total_time': progress['elapsed_time'],
            'output_location': str(self.output_dir),
            'session_id': progress['session_id'],
            'statistics': self.state.state['statistics'].copy()
        }
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get current state summary for status checking."""
        return self.state.get_progress_summary()
    
    async def cleanup_failed_urls(self) -> Dict[str, Any]:
        """Retry failed URLs from previous runs."""
        failed_urls = self.state.state.get('failed_urls', [])
        
        if not failed_urls:
            return {'message': 'No failed URLs to retry'}
        
        self.logger.info(f"Retrying {len(failed_urls)} failed URLs...")
        
        # Clear failed URLs and retry
        self.state.state['failed_urls'] = []
        
        retry_results = []
        for url in failed_urls:
            try:
                post_data = await self.content_extractor.extract_post_content(url)
                if post_data:
                    self.state.mark_url_completed(url, post_data)
                    retry_results.append({'url': url, 'success': True})
                else:
                    self.state.mark_url_failed(url, "No content extracted on retry")
                    retry_results.append({'url': url, 'success': False, 'error': 'No content'})
            except Exception as e:
                self.state.mark_url_failed(url, str(e))
                retry_results.append({'url': url, 'success': False, 'error': str(e)})
        
        successful_retries = sum(1 for result in retry_results if result['success'])
        
        return {
            'retried_urls': len(failed_urls),
            'successful_retries': successful_retries,
            'results': retry_results
        }