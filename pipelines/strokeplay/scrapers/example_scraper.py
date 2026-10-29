"""
Example scraper showing how to add new data sources.
This is a template for creating additional scrapers.
"""

from datetime import datetime
from typing import List

from models import ScrapingResult
from scrapers.base_scraper import BaseScraper


class ExampleScraper(BaseScraper):
    """
    Example scraper for demonstration purposes.

    To add a new scraper:
    1. Copy this file and rename it
    2. Implement the required methods
    3. Register it in ScraperOrchestrator
    """

    def __init__(self, config):
        super().__init__(config)
        # Add any scraper-specific initialization here

    def validate_config(self) -> bool:
        """Validate configuration for this scraper."""
        # Check if required config fields exist
        required_fields = ["example_url", "api_key"]  # Customize for your needs
        for field in required_fields:
            if not hasattr(self.config, field) or not getattr(self.config, field):
                self.logger.error(f"Missing required config field: {field}")
                return False
        return True

    def run(self) -> ScrapingResult:
        """
        Main scraping logic.

        This is where you implement your actual scraping:
        - Connect to data source
        - Extract data
        - Process and clean data
        - Return results
        """
        try:
            # Example: simulate scraping some data
            self.logger.info("Starting example scraper...")

            # Your scraping logic would go here
            # For example:
            # - HTTP requests to APIs
            # - Database queries
            # - File parsing
            # - Web scraping with Selenium

            # Simulate finding some scores
            scores = [12.5, 15.2, 8.7, 20.1]

            self.logger.info(f"Example scraper completed, found {len(scores)} scores")

            return ScrapingResult(
                success=True, scores=scores, timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            self.logger.error(f"Example scraper failed: {e}")
            return ScrapingResult(
                success=False,
                scores=[],
                error_message=str(e),
                timestamp=datetime.now().isoformat(),
            )

    def get_description(self) -> str:
        """Get description of what this scraper does."""
        return "Example scraper for demonstration purposes"


# Example of how to add configuration for this scraper
# Add to config.yaml:
"""
example_scraper:
  enabled: true
  example_url: "https://api.example.com/data"
  api_key: "your_api_key_here"
  timeout: 30
  retry_attempts: 3
"""

# Add to .env (if needed):
# EXAMPLE_API_KEY=your_actual_api_key



