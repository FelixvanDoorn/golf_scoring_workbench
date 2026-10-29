#!/usr/bin/env python3
"""
Example script showing how to use the models.
"""

from pipelines.strokeplay.models import ScraperConfig, GolfScore, ScrapingResult, LoginResult


def example_scraper_config():
    """Example of creating and using ScraperConfig."""
    print("=== ScraperConfig Example ===\n")

    # Create a configuration
    config = ScraperConfig(
        email="user@example.com",
        password="secret123",
        timeout=15,
        headless=True,
        log_level="DEBUG",
    )

    print(f"✓ Configuration created:")
    print(f"  Email: {config.email}")
    print(f"  Timeout: {config.timeout}s")
    print(f"  Headless: {config.headless}")
    print(f"  Log Level: {config.log_level}")

    return config


def example_golf_score():
    """Example of creating and using GolfScore."""
    print("\n=== GolfScore Example ===\n")

    # Create a golf score
    score = GolfScore(
        date="2024-01-15",
        course="Golf Club Amsterdam",
        score=78,
        differential=12.5,
        status="verified",
    )

    print(f"✓ Golf score created:")
    print(f"  Date: {score.date}")
    print(f"  Course: {score.course}")
    print(f"  Score: {score.score}")
    print(f"  Differential: {score.differential}")
    print(f"  Status: {score.status}")

    return score


def example_scraping_result():
    """Example of creating and using ScrapingResult."""
    print("\n=== ScrapingResult Example ===\n")

    # Create a successful scraping result
    success_result = ScrapingResult(
        success=True, scores=[12.5, 15.2, 8.7, 20.1], timestamp="2024-01-15T10:30:00Z"
    )

    print(f"✓ Successful scraping result:")
    print(f"  Success: {success_result.success}")
    print(f"  Scores found: {success_result.total_scores_found}")
    print(f"  Timestamp: {success_result.timestamp}")

    # Create a failed scraping result
    failed_result = ScrapingResult(
        success=False,
        scores=[],
        error_message="Website is down",
        timestamp="2024-01-15T10:30:00Z",
    )

    print(f"\n✗ Failed scraping result:")
    print(f"  Success: {failed_result.success}")
    print(f"  Error: {failed_result.error_message}")
    print(f"  Scores found: {failed_result.total_scores_found}")

    return success_result, failed_result


def example_login_result():
    """Example of creating and using LoginResult."""
    print("\n=== LoginResult Example ===\n")

    # Successful login
    success_login = LoginResult(success=True, timestamp="2024-01-15T10:30:00Z")

    print(f"✓ Successful login:")
    print(f"  Success: {success_login.success}")
    print(f"  Timestamp: {success_login.timestamp}")

    # Failed login
    failed_login = LoginResult(
        success=False,
        error_message="Invalid credentials",
        timestamp="2024-01-15T10:30:00Z",
    )

    print(f"\n✗ Failed login:")
    print(f"  Success: {failed_login.success}")
    print(f"  Error: {failed_login.error_message}")
    print(f"  Timestamp: {failed_login.timestamp}")

    return success_login, failed_login


def main():
    """Run all model examples."""
    print("🎯 Golf.nl Scraper Models Examples\n")

    # Example 1: ScraperConfig
    config = example_scraper_config()

    # Example 2: GolfScore
    score = example_golf_score()

    # Example 3: ScrapingResult
    success_result, failed_result = example_scraping_result()

    # Example 4: LoginResult
    success_login, failed_login = example_login_result()

    print(f"\n=== Summary ===")
    print(f"✓ ScraperConfig: {type(config).__name__}")
    print(f"✓ GolfScore: {type(score).__name__}")
    print(f"✓ ScrapingResult: {type(success_result).__name__}")
    print(f"✓ LoginResult: {type(success_login).__name__}")

    print(f"\n🎉 All model examples worked!")
    print(f"\nYou can now use these models in your scraper:")
    print(f"  from models import ScraperConfig, GolfScore, ScrapingResult, LoginResult")


if __name__ == "__main__":
    main()



