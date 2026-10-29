"""Tests for error chaining in pipelines.strokeplay.config_manager.

Config files live in tmp_path. .env loading is patched out so no credentials are read.
"""

from pathlib import Path

import pytest
import yaml

from pipelines.strokeplay import config_manager
from pipelines.strokeplay.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure no .env file is ever parsed during these tests."""

    def _fail(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise AssertionError("dotenv_values must not be called")

    monkeypatch.setattr(config_manager, "dotenv_values", _fail)


def test_invalid_yaml_raises_value_error_chained_from_yaml_error(tmp_path: Path) -> None:
    """Invalid YAML raises ValueError whose __cause__ is the original yaml.YAMLError."""
    (tmp_path / "config.yaml").write_text("urls: [unclosed\n  base: :\n", encoding="utf-8")
    manager = ConfigManager(config_dir=tmp_path)

    with pytest.raises(ValueError, match="Invalid YAML configuration") as exc_info:
        manager.load_config()

    assert isinstance(exc_info.value.__cause__, yaml.YAMLError)


def test_missing_yaml_raises_file_not_found(tmp_path: Path) -> None:
    """A missing config.yaml raises FileNotFoundError before any .env loading."""
    manager = ConfigManager(config_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.load_config()
