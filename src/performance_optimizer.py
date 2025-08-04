"""Performance optimization utilities for the archive process."""

import asyncio
import logging
import time
import gc
import psutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib

from .config import ArchiveConfig


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    memory_usage_mb: float
    cpu_usage_percent: float
    execution_time_seconds: float
    operations_per_second: float
    peak_memory_mb: float
    total_operations: int


class MemoryMonitor:
    """Monitors memory usage during archive operations."""
    
    def __init__(self, warning_threshold_mb: float = 1024):
        self.warning_threshold_mb = warning_threshold_mb
        self.peak_usage_mb = 0
        self.measurements = []
        self.logger = logging.getLogger("squarespace_archiver.memory_monitor")
        
    def get_current_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        memory_info = process.memory_info()
        usage_mb = memory_info.rss / 1024 / 1024
        
        self.peak_usage_mb = max(self.peak_usage_mb, usage_mb)
        self.measurements.append({
            'timestamp': time.time(),
            'usage_mb': usage_mb
        })
        
        if usage_mb > self.warning_threshold_mb:
            self.logger.warning(f"High memory usage: {usage_mb:.1f} MB")
        
        return usage_mb
    
    def force_cleanup(self):
        """Force garbage collection and memory cleanup."""
        gc.collect()
        self.logger.info("Forced garbage collection")


class CacheManager:
    """Manages caching of frequently accessed data to improve performance."""
    
    def __init__(self, max_cache_size: int = 1000):
        self.max_cache_size = max_cache_size
        self._cache = {}
        self._access_times = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("squarespace_archiver.cache_manager")
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key in self._cache:
                self._access_times[key] = time.time()
                return self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Set item in cache."""
        with self._lock:
            # Clean cache if it's full
            if len(self._cache) >= self.max_cache_size:
                self._evict_oldest()
            
            self._cache[key] = value
            self._access_times[key] = time.time()
    
    def _evict_oldest(self):
        """Evict the least recently used item."""
        if not self._access_times:
            return
        
        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[oldest_key]
        del self._access_times[oldest_key]
    
    def clear(self):
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_cache_size,
                'utilization': len(self._cache) / self.max_cache_size
            }


class BatchProcessor:
    """Processes operations in batches for better performance."""
    
    def __init__(self, batch_size: int = 10, max_workers: int = 4):
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.logger = logging.getLogger("squarespace_archiver.batch_processor")
    
    async def process_async_batch(self, items: List[Any], processor_func: Callable, 
                                 semaphore_limit: int = 5) -> List[Any]:
        """Process items in async batches with concurrency control."""
        semaphore = asyncio.Semaphore(semaphore_limit)
        results = []
        
        async def process_item(item):
            async with semaphore:
                try:
                    return await processor_func(item)
                except Exception as e:
                    self.logger.error(f"Batch processing error for {item}: {e}")
                    return None
        
        # Process in batches
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_tasks = [process_item(item) for item in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Filter out None results and exceptions
            valid_results = [r for r in batch_results if r is not None and not isinstance(r, Exception)]
            results.extend(valid_results)
            
            # Small delay between batches to be respectful
            await asyncio.sleep(0.1)
        
        return results
    
    def process_sync_batch(self, items: List[Any], processor_func: Callable) -> List[Any]:
        """Process items in sync batches using thread pool."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for i in range(0, len(items), self.batch_size):
                batch = items[i:i + self.batch_size]
                
                # Submit batch to thread pool
                futures = [executor.submit(processor_func, item) for item in batch]
                
                # Collect results
                for future in futures:
                    try:
                        result = future.result(timeout=30)  # 30 second timeout
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        self.logger.error(f"Batch processing error: {e}")
        
        return results


class PerformanceOptimizer:
    """Main performance optimization coordinator."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.performance_optimizer")
        
        # Initialize components
        self.memory_monitor = MemoryMonitor(warning_threshold_mb=1024)
        self.cache_manager = CacheManager(max_cache_size=1000)
        self.batch_processor = BatchProcessor(batch_size=5, max_workers=3)
        
        # Performance tracking
        self.start_time = None
        self.operation_count = 0
        self.metrics_history = []
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.operation_count = 0
        self.logger.info("Performance monitoring started")
    
    def record_operation(self):
        """Record completion of an operation."""
        self.operation_count += 1
        
        # Check memory usage periodically
        if self.operation_count % 10 == 0:
            self.memory_monitor.get_current_usage()
            
            # Force cleanup if memory usage is high
            if self.memory_monitor.peak_usage_mb > 2048:  # 2GB threshold
                self.memory_monitor.force_cleanup()
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        if self.start_time is None:
            self.start_monitoring()
        
        elapsed_time = time.time() - self.start_time
        memory_usage = self.memory_monitor.get_current_usage()
        
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        ops_per_second = self.operation_count / elapsed_time if elapsed_time > 0 else 0
        
        return PerformanceMetrics(
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_percent,
            execution_time_seconds=elapsed_time,
            operations_per_second=ops_per_second,
            peak_memory_mb=self.memory_monitor.peak_usage_mb,
            total_operations=self.operation_count
        )
    
    def optimize_extraction_batch(self, urls: List[str]) -> List[str]:
        """Optimize URL batch for extraction based on performance constraints."""
        current_memory = self.memory_monitor.get_current_usage()
        
        # Reduce batch size if memory usage is high
        if current_memory > 1500:  # 1.5GB
            reduced_batch_size = max(1, len(urls) // 3)
            self.logger.info(f"Reducing batch size to {reduced_batch_size} due to high memory usage")
            return urls[:reduced_batch_size]
        elif current_memory > 1000:  # 1GB
            reduced_batch_size = max(1, len(urls) // 2)
            return urls[:reduced_batch_size]
        
        return urls
    
    async def optimize_async_operations(self, items: List[Any], processor_func: Callable) -> List[Any]:
        """Process items with performance optimizations."""
        # Optimize batch size based on current performance
        current_metrics = self.get_current_metrics()
        
        # Adjust concurrency based on system resources
        if current_metrics.memory_usage_mb > 1024:
            semaphore_limit = 3  # Reduce concurrency
        elif current_metrics.cpu_usage_percent > 80:
            semaphore_limit = 2  # Further reduce if CPU is stressed
        else:
            semaphore_limit = 5  # Normal concurrency
        
        return await self.batch_processor.process_async_batch(
            items, processor_func, semaphore_limit
        )
    
    def get_cache_key(self, url: str, content_preview: str = "") -> str:
        """Generate cache key for URL and content."""
        combined = f"{url}|{content_preview[:100]}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def cache_content(self, url: str, content: Dict[str, Any]):
        """Cache extracted content."""
        cache_key = self.get_cache_key(url, content.get('content_html', '')[:100])
        self.cache_manager.set(cache_key, content)
    
    def get_cached_content(self, url: str, content_preview: str = "") -> Optional[Dict[str, Any]]:
        """Get cached content if available."""
        cache_key = self.get_cache_key(url, content_preview)
        return self.cache_manager.get(cache_key)
    
    def optimize_file_operations(self, file_path: Path, content: str) -> bool:
        """Optimize file writing operations."""
        try:
            # Write in chunks for large files
            if len(content) > 1024 * 1024:  # 1MB
                with open(file_path, 'w', encoding='utf-8', buffering=8192) as f:
                    chunk_size = 64 * 1024  # 64KB chunks
                    for i in range(0, len(content), chunk_size):
                        f.write(content[i:i + chunk_size])
            else:
                # Normal write for smaller files
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"File operation optimization failed: {e}")
            return False
    
    def save_performance_report(self, output_dir: Path):
        """Save performance report to file."""
        metrics = self.get_current_metrics()
        cache_stats = self.cache_manager.get_stats()
        
        report = {
            'timestamp': time.time(),
            'metrics': {
                'memory_usage_mb': metrics.memory_usage_mb,
                'peak_memory_mb': metrics.peak_memory_mb,
                'cpu_usage_percent': metrics.cpu_usage_percent,
                'execution_time_seconds': metrics.execution_time_seconds,
                'operations_per_second': metrics.operations_per_second,
                'total_operations': metrics.total_operations
            },
            'cache_stats': cache_stats,
            'memory_measurements': self.memory_monitor.measurements[-100:],  # Last 100 measurements
            'recommendations': self._generate_recommendations(metrics)
        }
        
        report_file = output_dir / 'performance_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Performance report saved to {report_file}")
    
    def _generate_recommendations(self, metrics: PerformanceMetrics) -> List[str]:
        """Generate performance recommendations based on metrics."""
        recommendations = []
        
        if metrics.peak_memory_mb > 2048:
            recommendations.append("Consider reducing batch sizes to lower memory usage")
        
        if metrics.operations_per_second < 0.5:
            recommendations.append("Archive process is running slowly - check network connectivity")
        
        if metrics.cpu_usage_percent > 90:
            recommendations.append("High CPU usage detected - consider reducing concurrency")
        
        cache_stats = self.cache_manager.get_stats()
        if cache_stats['utilization'] < 0.3:
            recommendations.append("Cache is underutilized - consider enabling more aggressive caching")
        
        if not recommendations:
            recommendations.append("Performance looks good - no specific recommendations")
        
        return recommendations
    
    def cleanup(self):
        """Clean up resources and save final report."""
        self.cache_manager.clear()
        self.memory_monitor.force_cleanup()
        self.logger.info("Performance optimizer cleanup completed")