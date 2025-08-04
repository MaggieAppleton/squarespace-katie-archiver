"""Logging configuration for the Squarespace Blog Archiver."""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True
) -> logging.Logger:
    """Set up comprehensive logging for the archiver.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        console_output: Whether to output to console
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("squarespace_archiver")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log debug to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_default_log_file() -> Path:
    """Get default log file path with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("logs") / f"archiver_{timestamp}.log"


class ProgressLogger:
    """Helper class for logging progress updates."""
    
    def __init__(self, logger: logging.Logger, total_items: int, description: str = "Processing"):
        self.logger = logger
        self.total_items = total_items
        self.description = description
        self.current_item = 0
        self.last_percentage = -1
    
    def update(self, increment: int = 1) -> None:
        """Update progress and log if percentage changed significantly."""
        self.current_item += increment
        percentage = int((self.current_item / self.total_items) * 100)
        
        # Log every 10% or at completion
        if percentage >= self.last_percentage + 10 or self.current_item == self.total_items:
            self.logger.info(
                f"{self.description}: {self.current_item}/{self.total_items} "
                f"({percentage}%) completed"
            )
            self.last_percentage = percentage
    
    def complete(self) -> None:
        """Mark progress as complete."""
        self.logger.info(f"{self.description}: Completed all {self.total_items} items")