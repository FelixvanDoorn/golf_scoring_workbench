"""
Configuration manager for the Golf.nl scraper.
Handles loading configuration from YAML and .env files.
"""

from dotenv import dotenv_values
from pipelines.strokeplay.models import ScraperConfig
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class ConfigManager:
    """Manages configuration loading from YAML and .env files."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the configuration manager.

        Args:
            config_dir: Directory containing config files.
                       Defaults to the directory of this script.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent

        self.config_dir = config_dir
        self.yaml_config: Dict[str, Any] = {}
        self.env_config: Dict[str, Any] = {}

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from both YAML and .env files.

        Returns:
            Merged configuration dictionary with .env values taking precedence.

        Raises:
            FileNotFoundError: If required config files are missing.
            ValueError: If required configuration fields are missing.
        """
        # Load YAML configuration
        self._load_yaml_config()

        # Load environment configuration
        self._load_env_config()

        # Merge configurations (env takes precedence)
        merged_config = self._merge_configs()

        # Validate required fields
        self._validate_config(merged_config)

        return merged_config

    def _load_yaml_config(self) -> None:
        """Load configuration from config.yaml file."""
        yaml_path = self.config_dir / "config.yaml"

        if not yaml_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

        try:
            with open(yaml_path, "r", encoding="utf-8") as file:
                self.yaml_config = yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")

    def _load_env_config(self) -> None:
        """Load configuration from .env file."""
        env_path = self.config_dir / ".env"

        if not env_path.exists():
            raise FileNotFoundError(f"Environment file not found: {env_path}")

        self.env_config = dotenv_values(env_path)

    def _merge_configs(self) -> Dict[str, Any]:
        """
        Merge YAML and .env configurations.
        Environment variables take precedence over YAML values.
        """
        merged = self._flatten_dict(self.yaml_config)

        # Override with .env values
        for key, value in self.env_config.items():
            if value:  # Only override if value is not empty
                merged[key] = value

        return merged

    def _flatten_dict(
        self, d: Dict[str, Any], parent_key: str = "", sep: str = "_"
    ) -> Dict[str, Any]:
        """
        Flatten nested dictionary structure.

        Example:
            Input:  {'urls': {'base': 'https://example.com'}}
            Output: {'urls_base': 'https://example.com'}
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate that required configuration fields are present."""
        required_fields = ["email", "password"]
        missing_fields = [field for field in required_fields if not config.get(field)]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports nested keys with underscore separator)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def reload(self) -> None:
        """Reload configuration from files."""
        self.yaml_config = {}
        self.env_config = {}
        self.config = self.load_config()

    @property
    def config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        if not hasattr(self, "_config"):
            self._config = self.load_config()
        return self._config


def create_scraper_config(config_dict: Dict[str, Any]) -> ScraperConfig:
    """
    Create a ScraperConfig object from configuration dictionary.

    Args:
        config_dict: Configuration dictionary from ConfigManager

    Returns:
        ScraperConfig object
    """

    return ScraperConfig(
        email=config_dict["email"],
        password=config_dict["password"],
        base_url=config_dict.get("urls_base", "https://mijn.golf.nl"),
        login_url=config_dict.get("urls_login", "https://mijn.golf.nl/login"),
        scores_url=config_dict.get(
            "urls_scores", "https://mijn.golf.nl/mijn-spel/scores"
        ),
        timeout=config_dict.get("scraper_timeout", 10),
        retry_attempts=config_dict.get("scraper_retry_attempts", 3),
        implicit_wait=config_dict.get("scraper_implicit_wait", 5),
        headless=config_dict.get("scraper_headless", False),
        user_agent=config_dict.get(
            "browser_user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        ),
        window_size=config_dict.get("browser_window_size", "1920x1080"),
        disable_images=config_dict.get("browser_disable_images", True),
        disable_javascript=config_dict.get("browser_disable_javascript", False),
        log_level=config_dict.get("logging_level", "INFO"),
        log_format=config_dict.get(
            "logging_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        score_pattern=config_dict.get(
            "extraction_score_pattern", r"<div>SD([\d,]+)\xa0"
        ),
    )


def load_config(config_dir: Path | None = None) -> ScraperConfig:
    """
    Convenience function to load configuration and create ScraperConfig.

    Args:
        config_dir: Directory containing config.yaml and .env.
                   Defaults to the directory of this module.

    Returns:
        ScraperConfig object

    Raises:
        FileNotFoundError: If required config files are missing.
        ValueError: If required configuration fields are missing.
    """
    config_manager = ConfigManager(config_dir)
    config_dict = config_manager.load_config()
    return create_scraper_config(config_dict)
