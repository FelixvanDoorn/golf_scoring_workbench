#!/usr/bin/env python3
"""
Debug script to save HTML from pages you're scraping.
Use this to inspect the HTML structure and find the right selectors.
"""

from pipelines.strokeplay.config_manager import load_config
from pipelines.strokeplay.scrapers.golf_nl_scraper import GolfNLScraper
from selenium.webdriver.common.by import By
from pathlib import Path

# Load configuration
config = load_config()
scraper = GolfNLScraper(config)

try:
    # Setup driver
    scraper.driver = scraper._setup_driver()

    # Login
    if scraper.login():
        print("✓ Logged in successfully")

        # Navigate to the page you want to inspect
        scraper.driver.get(config.scores_url)

        # Wait for content to load
        scraper._wait_for_element(By.CLASS_NAME, "c-scores")

        # Save the entire page HTML
        scraper.save_page_html("full_page.html")
        print("✓ Saved full page HTML to full_page.html")

        # Save a specific element's HTML
        score_elements = scraper.driver.find_elements(By.CLASS_NAME, "c-module")
        if score_elements:
            scraper.save_page_html(
                "first_score_element.html", element=score_elements[0]
            )
            print("✓ Saved first score element HTML to first_score_element.html")

        # You can also save the page source directly
        page_source = scraper.driver.page_source
        output_path = Path(__file__).parent / "page_source.html"
        output_path.write_text(page_source, encoding="utf-8")
        print(f"✓ Saved page source to {output_path}")

    else:
        print("✗ Login failed")

finally:
    if scraper.driver:
        scraper.driver.quit()
