"""
Base scraper class that defines the interface for all golf data scrapers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pipelines.strokeplay.models import ScraperConfig, ScrapingResult


class BaseScraper(ABC):
    """Abstract base class for all golf data scrapers."""
    
    def __init__(self, config: ScraperConfig):
        """
        Initialize the base scraper.
        
        Args:
            config: Configuration for the scraper
        """
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    def run(self) -> ScrapingResult:
        """
        Run the scraper and return results.
        
        Returns:
            ScrapingResult with the scraping outcome
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the configuration is sufficient for this scraper.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        pass
    
    def get_name(self) -> str:
        """Get the name of this scraper."""
        return self.name
    
    def get_description(self) -> str:
        """Get a description of what this scraper does."""
        return f"{self.name} - Golf data scraper"
    
    def is_enabled(self) -> bool:
        """Check if this scraper is enabled in the configuration."""
        # Override in subclasses if needed
        return True



