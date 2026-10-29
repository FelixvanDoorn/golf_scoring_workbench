"""
Golf.nl scraper implementation.
"""

import logging
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from pipelines.strokeplay.models import LoginResult, ScraperConfig, ScrapingResult
from pipelines.strokeplay.scrapers.base_scraper import BaseScraper


class GolfNLScraper(BaseScraper):
    """Golf.nl website scraper."""

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.driver: webdriver.Chrome = None
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger(__name__)

        # Use config values for logging
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logger.setLevel(log_level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(self.config.log_format)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def validate_config(self) -> bool:
        """Validate that the configuration is sufficient for this scraper."""
        required_fields = ["email", "password", "login_url", "scores_url"]
        for field in required_fields:
            if not hasattr(self.config, field) or not getattr(self.config, field):
                self.logger.error(f"Missing required config field: {field}")
                return False
        return True

    def _setup_driver(self) -> webdriver.Chrome:
        """Initialize and configure the Chrome WebDriver."""
        try:
            service = ChromeService(ChromeDriverManager().install())

            # Configure Chrome options based on config
            options = webdriver.ChromeOptions()

            if self.config.headless:
                options.add_argument("--headless")

            if self.config.disable_images:
                options.add_argument("--disable-images")

            if self.config.disable_javascript:
                options.add_argument("--disable-javascript")

            options.add_argument(f"--user-agent={self.config.user_agent}")
            options.add_argument(f"--window-size={self.config.window_size}")

            driver = webdriver.Chrome(service=service, options=options)
            driver.implicitly_wait(self.config.implicit_wait)

            return driver
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def _wait_for_element(self, by: By, value: str, timeout: int = None) -> any:
        """Wait for an element to be present on the page."""
        timeout = timeout or self.config.timeout
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.error(f"Timeout waiting for element: {value}")
            raise

    def login(self) -> LoginResult:
        """Log in to the Golf.nl website."""
        try:
            self.logger.info("Attempting to log in to Golf.nl")

            # Navigate to login page
            self.driver.get(self.config.login_url)

            # Find and fill email field
            email_field = self.driver.find_element(By.NAME, "email")
            email_field.clear()
            email_field.send_keys(self.config.email)

            # Find and fill password field
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(self.config.password)

            # Submit login form
            login_button = self.driver.find_element(By.CLASS_NAME, "button")
            login_button.click()

            # Wait for successful login (redirect or dashboard element)
            self._wait_for_element(By.CLASS_NAME, "c-dashboard", timeout=15)

            self.logger.info("Successfully logged in to Golf.nl")
            return LoginResult(success=True, timestamp=datetime.now().isoformat())

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            return LoginResult(
                success=False,
                error_message=str(e),
                timestamp=datetime.now().isoformat(),
            )

    def _extract_score_details(self, score_details_html: str) -> dict[str, Any]:
        """
        Extract key-value pairs from a score details block.

        Structure: Keys are in divs with class "c-score__legend"
                   Values are in divs with class "c-score__content"

        Args:
            score_details_html: HTML content of a c-score__details div

        Returns:
            Dictionary with keys from c-score__legend and values from c-score__content
        """
        try:
            soup = BeautifulSoup(score_details_html, "html.parser")

            # Find the main score details container
            details_container = soup.find("div", class_="c-score__details")
            if not details_container:
                # If the HTML is just the container itself, use the whole soup
                details_container = soup

            # Find all legend (key) elements
            score_details_content_divs = details_container.find_all(
                "div", class_="c-score__details__content"
            )

            self.logger.info(f"Found {len(score_details_content_divs)} score details content divs")

            score_data = {}

            # For each legend, find its corresponding content
            for content_div in score_details_content_divs:
                key_div = content_div.find("div", class_="c-score__details__label")
                value_div = content_div.find("div", class_="c-score__details__text")

                if key_div and value_div:
                    key = key_div.get_text(strip=True)
                    value = value_div.get_text(strip=True)

                    if key:
                        score_data[key] = value

            return score_data

        except Exception as e:
            self.logger.warning(f"Error extracting score details: {e}")
            return {}

    def scrape_scores(self) -> list[dict[str, Any]]:
        """
        Scrape golf scores from the website.

        Returns:
            List of dictionaries containing structured score data
        """
        try:
            self.logger.info("Navigating to scores page")
            self.driver.get(self.config.scores_url)

            # Wait for scores to load
            self._wait_for_element(By.CLASS_NAME, "c-scores")

            # Find all score detail blocks
            score_detail_elements = self.driver.find_elements(By.CLASS_NAME, "c-score__details")
            self.logger.info(f"Found {len(score_detail_elements)} score detail blocks")
            all_scores = []

            for i, score_detail_element in enumerate(score_detail_elements):
                try:
                    # Get HTML of the score details block
                    score_html = score_detail_element.get_attribute("outerHTML")

                    # Extract structured key-value pairs
                    score_data = self._extract_score_details(score_html)

                    if score_data:
                        all_scores.append(score_data)
                        self.logger.debug(
                            f"Score {i + 1}: Extracted {len(score_data)} fields - {list(score_data.keys())}"
                        )
                    else:
                        self.logger.warning(f"Score {i + 1}: No data extracted")

                except Exception as e:
                    self.logger.warning(f"Error processing score element {i + 1}: {e}")
                    continue

            self.logger.info(f"Successfully extracted {len(all_scores)} score records")

            # Log sample of extracted data for debugging
            if all_scores and self.logger.level <= logging.DEBUG:
                sample = all_scores[0]
                self.logger.debug(f"Sample score data keys: {list(sample.keys())}")

            return all_scores

        except Exception as e:
            self.logger.error(f"Error scraping scores: {e}")
            return []

    def run(self) -> ScrapingResult:
        """Main method to run the scraper."""
        if not self.validate_config():
            return ScrapingResult(
                success=False,
                score_details=[],
                error_message="Invalid configuration",
                timestamp=datetime.now().isoformat(),
            )

        try:
            self.driver = self._setup_driver()

            # Attempt login
            login_result = self.login()
            if not login_result.success:
                return ScrapingResult(
                    success=False,
                    score_details=[],
                    error_message=f"Login failed: {login_result.error_message}",
                    timestamp=datetime.now().isoformat(),
                )

            # Scrape scores
            scores = self.scrape_scores()

            return ScrapingResult(
                success=True, score_details=scores, timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            self.logger.error(f"Scraper failed: {e}")
            return ScrapingResult(
                success=False,
                score_details=[],
                error_message=str(e),
                timestamp=datetime.now().isoformat(),
            )

        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("WebDriver closed")
