# Golf.nl Scraper

A modular, robust web scraper for extracting golf scores and statistics from Golf.nl.

## Features

- **Modular Design**: Clean separation of concerns with dedicated classes for different responsibilities
- **Robust Error Handling**: Comprehensive exception handling and logging
- **Configuration Management**: Environment-based configuration with validation
- **Type Safety**: Full type hints for better code quality and IDE support
- **Logging**: Detailed logging for debugging and monitoring
- **Resource Management**: Proper cleanup of WebDriver resources

## Structure

```
scrapers/strokeplay/
├── models.py             # Data classes and models
├── golf_nl_scraper.py   # Main scraper implementation
├── golf_nl.py           # Original script (kept for reference)
├── config_manager.py     # Configuration management system
├── config.yaml          # Non-sensitive configuration
├── env.template         # Sensitive credentials template
├── test_config.py       # Configuration test script
└── README.md           # This file
```

## Key Improvements Over Original

### 1. **Separation of Concerns**
- `ScraperConfig`: Handles all configuration
- `GolfNLScraper`: Main scraping logic
- `GolfScore`: Data model for scores
- Utility functions for configuration loading

### 2. **Error Handling & Robustness**
- Try-catch blocks around all critical operations
- Proper WebDriver cleanup in finally blocks
- Timeout handling for web elements
- Graceful degradation when elements aren't found

### 3. **Configuration Management**
- **Hybrid Configuration**: YAML for settings, .env for credentials
- **Unified ScraperConfig**: All settings accessible through a single dataclass
- Environment file support with validation
- Default values for optional settings
- Clear error messages for missing configuration
- Easy to override YAML settings with environment variables

### 4. **Code Quality**
- **Modular Design**: Data classes separated into `models.py`
- Type hints throughout
- Comprehensive docstrings
- Consistent error handling patterns
- Logging at appropriate levels

## Setup

1. **Install Dependencies**
   ```bash
   uv sync   # from the repo root
   ```

2. **Configure Credentials**
   ```bash
   cp env.template .env
   # Edit .env with your Golf.nl credentials
   ```
   
   **Note**: The `.env` file contains only sensitive credentials. 
   Other configuration is in `config.yaml` and can be safely committed to version control.

3. **Test the Setup**
   ```bash
   python test_scraper.py
   ```

## Usage

### Basic Usage
```python
from golf_nl_scraper import GolfNLScraper, load_config

# Load configuration
config = load_config()

# Create and run scraper
scraper = GolfNLScraper(config)
scores = scraper.run()

print(f"Found {len(scores)} score differentials")
```

### Custom Configuration
```python
from golf_nl_scraper import ScraperConfig, GolfNLScraper

config = ScraperConfig(
    email="your@email.com",
    password="your_password",
    timeout=15,
    retry_attempts=5
)

scraper = GolfNLScraper(config)
scores = scraper.run()
```

### Running as Script
```bash
python golf_nl_scraper.py
```

## Models

The scraper uses several data classes defined in `models.py`:

- **`ScraperConfig`**: Complete configuration for the scraper
- **`GolfScore`**: Represents a single golf score entry
- **`ScrapingResult`**: Result of a scraping operation with metadata
- **`LoginResult`**: Result of a login attempt

## Configuration

The scraper uses a hybrid configuration system that creates a unified `ScraperConfig` object:

### **Sensitive Data (.env file)**
| Option | Required | Description |
|--------|----------|-------------|
| `email` | Yes | Your Golf.nl email address |
| `password` | Yes | Your Golf.nl password |

### **General Settings (config.yaml)**
| Category | Option | Default | Description |
|----------|--------|---------|-------------|
| **URLs** | `urls.base` | `https://mijn.golf.nl` | Base URL for the website |
| | `urls.login` | `https://mijn.golf.nl/login` | Login page URL |
| | `urls.scores` | `https://mijn.golf.nl/mijn-spel/scores` | Scores page URL |
| **Scraper** | `scraper.timeout` | `10` | Element wait timeout in seconds |
| | `scraper.retry_attempts` | `3` | Number of retry attempts |
| | `scraper.headless` | `false` | Run browser in headless mode |
| | `scraper.implicit_wait` | `5` | Implicit wait time for elements |
| **Browser** | `browser.window_size` | `1920x1080` | Browser window size |
| | `browser.disable_images` | `true` | Disable image loading for speed |
| | `browser.disable_javascript` | `false` | Disable JavaScript execution |
| | `browser.user_agent` | Custom | Custom user agent string |
| **Logging** | `logging.level` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| | `logging.format` | Custom | Log message format |
| **Extraction** | `extraction.score_pattern` | Custom | Regex pattern for score extraction |

### **Unified ScraperConfig Object**
All configuration is accessible through a single `ScraperConfig` dataclass:

```python
from config_manager import load_config
config = load_config()

# Access any configuration value
print(f"Timeout: {config.timeout}s")
print(f"Headless: {config.headless}")
print(f"Log Level: {config.log_level}")
```

### **Configuration Precedence**
1. `.env` file values (highest priority)
2. `config.yaml` values
3. Hardcoded defaults (lowest priority)

## Logging

The scraper provides detailed logging at different levels:

- **INFO**: General progress information
- **WARNING**: Non-critical issues (e.g., parsing failures)
- **ERROR**: Critical failures that prevent operation
- **DEBUG**: Detailed debugging information

## Error Handling

The scraper handles various error scenarios:

- **Network Issues**: Timeout handling and retry logic
- **Element Not Found**: Graceful fallbacks and informative error messages
- **Parsing Errors**: Continues processing other scores when individual ones fail
- **Authentication Failures**: Clear error messages for login issues

## Testing

Run the test suite to verify your setup:

```bash
# Test the configuration system
python test_config.py

# Test the models
python models_example.py
```

This will test:
- Configuration loading and validation
- Scraper initialization
- Model creation and usage
- Environment setup

## Future Enhancements

- **Data Export**: CSV/JSON export functionality
- **Database Integration**: Store scores in a database
- **Scheduling**: Run scraper on a schedule
- **API Endpoints**: REST API for accessing scraped data
- **More Score Data**: Extract additional golf statistics
- **Headless Mode**: Option to run without browser UI
- **Configuration Validation**: Schema validation for YAML config
- **Environment-specific Configs**: Different configs for dev/staging/prod

## Troubleshooting

### Common Issues

1. **ChromeDriver Issues**
   - The scraper automatically downloads ChromeDriver
   - Ensure Chrome browser is installed
   - Check Chrome version compatibility

2. **Login Failures**
   - Verify credentials in `.env` file
   - Check if Golf.nl requires 2FA
   - Ensure account is not locked

3. **Element Not Found**
   - Website structure may have changed
   - Check if selectors need updating
   - Verify page loads completely

### Debug Mode

Enable debug logging by modifying the logger level in `_setup_logging()`:

```python
logger.setLevel(logging.DEBUG)
```

## Contributing

When making changes:

1. Maintain the modular structure
2. Add type hints for new functions
3. Include comprehensive error handling
4. Update tests for new functionality
5. Follow the existing logging patterns
