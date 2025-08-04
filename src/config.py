"""Configuration management for the Squarespace Blog Archiver."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class ScrapingConfig:
    """Configuration for scraping behavior."""
    delay_between_requests: float = 2.5  # seconds
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds
    timeout: int = 30  # seconds
    user_agent: str = "Squarespace-Blog-Archiver/0.1.0"


@dataclass
class OutputConfig:
    """Configuration for output generation."""
    output_dir: str = "output"
    backup_existing: bool = True
    pretty_print_json: bool = True
    image_quality: int = 85  # for JPEG compression
    max_image_width: int = 1920  # pixels


@dataclass
class ArchiveConfig:
    """Main configuration class."""
    site_url: str = "https://www.thelibrarianedge.com/"
    scraping: ScrapingConfig = None
    output: OutputConfig = None
    
    def __post_init__(self):
        if self.scraping is None:
            self.scraping = ScrapingConfig()
        if self.output is None:
            self.output = OutputConfig()


class ConfigManager:
    """Manages loading and saving configuration."""
    
    DEFAULT_CONFIG_FILE = "archiver_config.json"
    
    @classmethod
    def load_config(cls, config_path: Optional[Path] = None) -> ArchiveConfig:
        """Load configuration from file or create default."""
        if config_path is None:
            config_path = Path(cls.DEFAULT_CONFIG_FILE)
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Reconstruct nested dataclasses
                scraping_data = data.get('scraping', {})
                output_data = data.get('output', {})
                
                config = ArchiveConfig(
                    site_url=data.get('site_url', 'https://www.thelibrarianedge.com/'),
                    scraping=ScrapingConfig(**scraping_data),
                    output=OutputConfig(**output_data)
                )
                
                logging.info(f"Loaded configuration from {config_path}")
                return config
                
            except (json.JSONDecodeError, TypeError) as e:
                logging.warning(f"Failed to load config from {config_path}: {e}")
                logging.info("Using default configuration")
        
        # Return default configuration
        return ArchiveConfig()
    
    @classmethod
    def save_config(cls, config: ArchiveConfig, config_path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        if config_path is None:
            config_path = Path(cls.DEFAULT_CONFIG_FILE)
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(config), f, indent=2, ensure_ascii=False)
            
            logging.info(f"Saved configuration to {config_path}")
            
        except IOError as e:
            logging.error(f"Failed to save config to {config_path}: {e}")
            raise