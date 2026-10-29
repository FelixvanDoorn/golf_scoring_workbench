"""Tests for pipelines.strokeplay.config_manager.

Every test reads config.yaml and .env from a tmp directory with fake values. The real
package .env is never opened, and no browser or network is touched.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pipelines.strokeplay import config_manager
from pipelines.strokeplay.config_manager import ConfigManager, load_config
from pipelines.strokeplay.models import ScraperConfig
from pipelines.strokeplay.scrapers import golf_nl_scraper
from pipelines.strokeplay.scrapers.golf_nl_scraper import GolfNLScraper

FAKE_EMAIL = "tester@example.invalid"
FAKE_CREDENTIAL = "not-a-real-password"
YAML_ONLY_CREDENTIAL = "from-yaml"

VALID_YAML = """\
urls:
  base: https://golf.example.invalid
  login: https://golf.example.invalid/login
  scores: https://golf.example.invalid/scores
scraper:
  timeout: 42
  headless: true
logging:
  level: DEBUG
browser:
  window_size: 800x600
"""

VALID_ENV = f"email={FAKE_EMAIL}\npassword={FAKE_CREDENTIAL}\n"


def _write(directory: Path, yaml_text: str | None, env_text: str | None) -> Path:
    """Write config.yaml and .env into directory; None skips that file."""
    directory.mkdir(parents=True, exist_ok=True)
    if yaml_text is not None:
        (directory / "config.yaml").write_text(yaml_text, encoding="utf-8")
    if env_text is not None:
        (directory / ".env").write_text(env_text, encoding="utf-8")
    return directory


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """A tmp config directory with a valid config.yaml and a fake .env."""
    return _write(tmp_path / "cfg", VALID_YAML, VALID_ENV)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep credentials from the developer's shell out of the tests."""
    for name in ("EMAIL", "PASSWORD", "email", "password"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def dotenv_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fail any test that makes config_manager read a .env outside tmp_path."""
    real_dotenv_values = config_manager.dotenv_values

    def guarded(path: Path, *args: Any, **kwargs: Any) -> dict[str, str | None]:
        assert Path(path).resolve().is_relative_to(tmp_path.resolve())
        return real_dotenv_values(path, *args, **kwargs)

    monkeypatch.setattr(config_manager, "dotenv_values", guarded)


def test_load_config_maps_yaml_and_env_into_scraper_config(config_dir: Path) -> None:
    config = load_config(config_dir)

    assert isinstance(config, ScraperConfig)
    assert config.email == FAKE_EMAIL
    assert config.password == FAKE_CREDENTIAL
    assert config.base_url == "https://golf.example.invalid"
    assert config.login_url == "https://golf.example.invalid/login"
    assert config.scores_url == "https://golf.example.invalid/scores"
    assert config.timeout == 42
    assert config.headless is True
    assert config.log_level == "DEBUG"
    assert config.window_size == "800x600"


def test_empty_yaml_falls_back_to_scraper_config_defaults(tmp_path: Path) -> None:
    directory = _write(tmp_path / "cfg", "", VALID_ENV)

    config = load_config(directory)

    assert config == ScraperConfig(email=FAKE_EMAIL, password=FAKE_CREDENTIAL)


def test_env_file_overrides_yaml_value(tmp_path: Path) -> None:
    directory = _write(tmp_path / "cfg", "email: yaml@example.invalid\n", VALID_ENV)

    config = load_config(directory)

    assert config.email == FAKE_EMAIL


def test_empty_env_value_does_not_override_yaml(tmp_path: Path) -> None:
    directory = _write(
        tmp_path / "cfg",
        f"password: {YAML_ONLY_CREDENTIAL}\n",
        f"email={FAKE_EMAIL}\npassword=\n",
    )

    config = load_config(directory)

    assert config.password == YAML_ONLY_CREDENTIAL


def test_process_environment_is_ignored(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("email", "decoy@example.invalid")
    monkeypatch.setenv("EMAIL", "decoy@example.invalid")

    config = load_config(config_dir)

    assert config.email == FAKE_EMAIL


def test_process_environment_does_not_fill_missing_env_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _write(tmp_path / "cfg", VALID_YAML, f"password={FAKE_CREDENTIAL}\n")
    monkeypatch.setenv("email", "decoy@example.invalid")
    monkeypatch.setenv("EMAIL", "decoy@example.invalid")

    with pytest.raises(ValueError, match="email"):
        load_config(directory)


def test_missing_yaml_raises_file_not_found(tmp_path: Path) -> None:
    directory = _write(tmp_path / "cfg", None, VALID_ENV)

    with pytest.raises(FileNotFoundError, match=r"config\.yaml"):
        load_config(directory)


def test_missing_env_raises_file_not_found(tmp_path: Path) -> None:
    directory = _write(tmp_path / "cfg", VALID_YAML, None)

    with pytest.raises(FileNotFoundError, match=r"\.env"):
        load_config(directory)


def test_invalid_yaml_raises_value_error(tmp_path: Path) -> None:
    directory = _write(tmp_path / "cfg", "urls: [unclosed\n  base: : :\n", VALID_ENV)

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_config(directory)


@pytest.mark.parametrize(
    ("missing", "env_text"),
    [
        ("email", f"password={FAKE_CREDENTIAL}\n"),
        ("password", f"email={FAKE_EMAIL}\n"),
    ],
)
def test_missing_required_field_raises_value_error(
    tmp_path: Path, missing: str, env_text: str
) -> None:
    directory = _write(tmp_path / "cfg", VALID_YAML, env_text)

    with pytest.raises(ValueError, match=missing):
        load_config(directory)


def test_config_manager_get_reads_flattened_keys(config_dir: Path) -> None:
    manager = ConfigManager(config_dir)

    assert manager.get("scraper_timeout") == 42
    assert manager.get("urls_base") == "https://golf.example.invalid"
    assert manager.get("nope", "fallback") == "fallback"


def test_default_config_dir_is_package_dir() -> None:
    # Only the attribute is inspected; loading would open the real .env.
    manager = ConfigManager()

    assert manager.config_dir == Path(config_manager.__file__).parent


def test_golf_nl_scraper_constructs_without_browser(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def trap(name: str) -> Callable[..., Any]:
        def _trap(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return _trap

    monkeypatch.setattr(golf_nl_scraper.webdriver, "Chrome", trap("webdriver.Chrome"))
    monkeypatch.setattr(golf_nl_scraper, "ChromeDriverManager", trap("ChromeDriverManager"))

    scraper = GolfNLScraper(load_config(config_dir))

    assert scraper.driver is None
    assert scraper.validate_config() is True
    assert calls == []
