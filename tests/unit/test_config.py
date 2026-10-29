#!/usr/bin/env python3
"""
Simple test script for the new configuration system.
"""

import sys
from pathlib import Path

# Add the current directory to the path
sys.path.append(str(Path(__file__).parent))

def test_config_loading():
    """Test that we can load configuration and create ScraperConfig."""
    try:
        from config_manager import load_config
        
        print("Testing configuration loading...")
        config = load_config()
        
        print(f"✓ Configuration loaded successfully!")
        print(f"  Email: {config.email}")
        print(f"  Base URL: {config.base_url}")
        print(f"  Timeout: {config.timeout}s")
        print(f"  Headless: {config.headless}")
        print(f"  Log Level: {config.log_level}")
        print(f"  User Agent: {config.user_agent[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return False


def test_scraper_creation():
    """Test that we can create a scraper with the config."""
    try:
        from config_manager import load_config
        from golf_nl_scraper import GolfNLScraper
        
        print("\nTesting scraper creation...")
        config = load_config()
        scraper = GolfNLScraper(config)
        
        print(f"✓ Scraper created successfully!")
        print(f"  Logger level: {scraper.logger.level}")
        print(f"  Config timeout: {scraper.config.timeout}")
        
        return True
        
    except Exception as e:
        print(f"✗ Scraper creation failed: {e}")
        return False


def main():
    """Run the configuration tests."""
    print("🧪 Testing Golf.nl Scraper Configuration System\n")
    
    # Test 1: Configuration loading
    config_ok = test_config_loading()
    
    # Test 2: Scraper creation
    scraper_ok = test_scraper_creation()
    
    print(f"\n=== Test Results ===")
    print(f"Configuration loading: {'✓ PASSED' if config_ok else '✗ FAILED'}")
    print(f"Scraper creation: {'✓ PASSED' if scraper_ok else '✗ FAILED'}")
    
    if config_ok and scraper_ok:
        print("\n🎉 All tests passed! The configuration system is working correctly.")
        print("\nYou can now use:")
        print("  from config_manager import load_config")
        print("  from golf_nl_scraper import GolfNLScraper")
        print("  config = load_config()")
        print("  scraper = GolfNLScraper(config)")
    else:
        print("\n⚠ Some tests failed. Check your configuration files.")
        print("\nMake sure you have:")
        print("  1. config.yaml (with your settings)")
        print("  2. .env (with your credentials)")


if __name__ == "__main__":
    main()



