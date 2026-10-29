#!/usr/bin/env python3
"""
Main orchestration script for running multiple golf data scrapers.
Controls which scrapers run and manages the overall scraping process.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add the current directory to the path
sys.path.append(str(Path(__file__).parent))

from config_manager import load_config
from models import ScrapingResult
from scrapers.base_scraper import BaseScraper
from scrapers.golf_nl_scraper import GolfNLScraper


class ScraperOrchestrator:
    """Orchestrates multiple scrapers with selective execution."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the orchestrator.

        Args:
            config_path: Path to configuration file (optional)
        """
        self.config = load_config()
        self.logger = self._setup_logging()
        self.scrapers: Dict[str, BaseScraper] = {}
        self.results: Dict[str, ScrapingResult] = {}

        # Register available scrapers
        self._register_scrapers()

    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the orchestrator."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _register_scrapers(self) -> None:
        """Register all available scrapers."""
        # Golf.nl scraper
        self.scrapers["golf_nl"] = GolfNLScraper(self.config)

        # Future scrapers can be added here:
        # self.scrapers['golf_handicap'] = GolfHandicapScraper(self.config)
        # self.scrapers['golf_netherlands'] = GolfNetherlandsScraper(self.config)
        # self.scrapers['golf_amateur'] = GolfAmateurScraper(self.config)

        self.logger.info(
            f"Registered {len(self.scrapers)} scrapers: {list(self.scrapers.keys())}"
        )

    def list_scrapers(self) -> List[str]:
        """List all available scrapers."""
        return list(self.scrapers.keys())

    def run_scraper(self, scraper_name: str) -> ScrapingResult:
        """
        Run a specific scraper.

        Args:
            scraper_name: Name of the scraper to run

        Returns:
            ScrapingResult from the scraper

        Raises:
            ValueError: If scraper name is not found
        """
        if scraper_name not in self.scrapers:
            raise ValueError(
                f"Scraper '{scraper_name}' not found. Available: {self.list_scrapers()}"
            )

        scraper = self.scrapers[scraper_name]
        self.logger.info(f"Starting scraper: {scraper_name}")

        try:
            result = scraper.run()
            self.results[scraper_name] = result
            self.logger.info(f"Scraper {scraper_name} completed successfully")
            return result

        except Exception as e:
            self.logger.error(f"Scraper {scraper_name} failed: {e}")
            error_result = ScrapingResult(
                success=False,
                scores=[],
                error_message=str(e),
                timestamp=datetime.now().isoformat(),
            )
            self.results[scraper_name] = error_result
            return error_result

    def run_scrapers(self, scraper_names: List[str]) -> Dict[str, ScrapingResult]:
        """
        Run multiple scrapers.

        Args:
            scraper_names: List of scraper names to run

        Returns:
            Dictionary of results by scraper name
        """
        self.logger.info(f"Running {len(scraper_names)} scrapers: {scraper_names}")

        for scraper_name in scraper_names:
            self.run_scraper(scraper_name)

        return self.results

    def run_all_scrapers(self) -> Dict[str, ScrapingResult]:
        """Run all available scrapers."""
        return self.run_scrapers(self.list_scrapers())

    def get_summary(self) -> Dict[str, any]:
        """Get a summary of all scraping results."""
        summary = {
            "total_scrapers": len(self.scrapers),
            "scrapers_run": len(self.results),
            "successful_scrapers": 0,
            "failed_scrapers": 0,
            "total_scores_found": 0,
            "results": {},
        }

        for scraper_name, result in self.results.items():
            summary["results"][scraper_name] = {
                "success": result.success,
                "scores_found": result.total_scores_found,
                "error": result.error_message,
                "timestamp": result.timestamp,
            }

            if result.success:
                summary["successful_scrapers"] += 1
                summary["total_scores_found"] += result.total_scores_found
            else:
                summary["failed_scrapers"] += 1

        return summary

    def print_summary(self) -> None:
        """Print a formatted summary of scraping results."""
        summary = self.get_summary()

        print(f"\n{'=' * 50}")
        print(f"SCRAPING SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total scrapers available: {summary['total_scrapers']}")
        print(f"Scrapers run: {summary['scrapers_run']}")
        print(f"Successful: {summary['successful_scrapers']}")
        print(f"Failed: {summary['failed_scrapers']}")
        print(f"Total scores found: {summary['total_scores_found']}")

        if summary["results"]:
            print(f"\nDetailed Results:")
            print(f"{'-' * 50}")
            for scraper_name, result in summary["results"].items():
                status = "✓ SUCCESS" if result["success"] else "✗ FAILED"
                print(f"{scraper_name:15} {status}")
                if result["success"]:
                    print(f"{'':15}  Scores: {result['scores_found']}")
                else:
                    print(f"{'':15}  Error: {result['error']}")


def main():
    """Main entry point with command line interface."""
    parser = argparse.ArgumentParser(description="Run golf data scrapers selectively")
    parser.add_argument(
        "--scrapers",
        "-s",
        nargs="+",
        help="Specific scrapers to run (e.g., golf_nl golf_handicap)",
    )
    parser.add_argument(
        "--all", "-a", action="store_true", help="Run all available scrapers"
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List all available scrapers"
    )
    parser.add_argument("--config", "-c", help="Path to configuration file")

    args = parser.parse_args()

    try:
        # Initialize orchestrator
        orchestrator = ScraperOrchestrator(args.config)

        # List scrapers if requested
        if args.list:
            print("Available scrapers:")
            for scraper in orchestrator.list_scrapers():
                print(f"  - {scraper}")
            return

        # Determine which scrapers to run
        if args.all:
            scraper_names = orchestrator.list_scrapers()
        elif args.scrapers:
            scraper_names = args.scrapers
        else:
            # Default: run golf_nl only
            scraper_names = ["golf_nl"]

        # Run scrapers
        results = orchestrator.run_scrapers(scraper_names)

        # Print summary
        orchestrator.print_summary()

        # Exit with error code if any scrapers failed
        failed_count = sum(1 for result in results.values() if not result.success)
        if failed_count > 0:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()



