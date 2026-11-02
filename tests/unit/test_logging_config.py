"""Tests that library code leaves logging alone and the CLI configures it once.

ScraperConfig is built with dummy credentials and load_config is patched, so no .env, config
file, browser, network or database is used.
"""

import logging
import sys
from collections.abc import Iterator

import pytest

from pipelines.strokeplay import scrape_strokeplay_data
from pipelines.strokeplay.models import ScraperConfig
from pipelines.strokeplay.scrape_strokeplay_data import (
    ScraperOrchestrator,
    configure_logging,
    main,
)
from pipelines.strokeplay.scrapers.golf_nl_scraper import GolfNLScraper

SCRAPER_LOGGER = "pipelines.strokeplay.scrapers.golf_nl_scraper"
CLI_LOGGER = "pipelines.strokeplay.scrape_strokeplay_data"
FAKE_EMAIL = "user@example.invalid"
FAKE_CREDENTIAL = "not-a-real-password"


def _dummy_config(**overrides: str) -> ScraperConfig:
    return ScraperConfig(email=FAKE_EMAIL, password=FAKE_CREDENTIAL, **overrides)


@pytest.fixture(autouse=True)
def restore_logging_state() -> Iterator[None]:
    """Snapshot and restore root and module logger handlers/levels around each test."""
    loggers = [
        logging.getLogger(),
        logging.getLogger(SCRAPER_LOGGER),
        logging.getLogger(CLI_LOGGER),
    ]
    saved = [(lg, list(lg.handlers), lg.level) for lg in loggers]
    saved_cli_handler = scrape_strokeplay_data._cli_handler
    try:
        yield
    finally:
        for lg, handlers, level in saved:
            lg.handlers[:] = handlers
            lg.setLevel(level)
        scrape_strokeplay_data._cli_handler = saved_cli_handler


def _cli_handlers() -> list[logging.Handler]:
    """Return the root handlers that configure_logging currently owns."""
    owned = scrape_strokeplay_data._cli_handler
    return [h for h in logging.getLogger().handlers if h is owned]


def test_golf_nl_scraper_init_does_not_touch_logging() -> None:
    """Constructing the scraper leaves root unchanged and adds no handler/level to its logger."""
    root = logging.getLogger()
    root_handlers, root_level = list(root.handlers), root.level

    GolfNLScraper(_dummy_config(log_level="DEBUG"))

    assert root.handlers == root_handlers
    assert root.level == root_level
    module_logger = logging.getLogger(SCRAPER_LOGGER)
    assert module_logger.handlers == []
    assert module_logger.level == logging.NOTSET


def test_orchestrator_init_does_not_touch_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructing the orchestrator leaves root and its module logger unchanged."""
    monkeypatch.setattr(
        scrape_strokeplay_data, "load_config", lambda: _dummy_config(log_level="DEBUG")
    )
    root = logging.getLogger()
    root_handlers, root_level = list(root.handlers), root.level

    ScraperOrchestrator()

    assert root.handlers == root_handlers
    assert root.level == root_level
    module_logger = logging.getLogger(CLI_LOGGER)
    assert module_logger.handlers == []
    assert module_logger.level == logging.NOTSET


def test_configure_logging_adds_one_handler_and_keeps_existing() -> None:
    """Repeated calls replace their own handler, set the level and keep foreign handlers."""
    root = logging.getLogger()
    foreign = logging.NullHandler()
    root.addHandler(foreign)
    before = [h for h in root.handlers if h not in _cli_handlers()]

    configure_logging("DEBUG", "%(levelname)s|%(message)s")

    assert root.level == logging.DEBUG
    added = [h for h in root.handlers if h not in before]
    assert len(added) == 1
    assert added == _cli_handlers()
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", None, None)
    assert added[0].format(record) == "INFO|hello"

    configure_logging("WARNING")

    assert root.level == logging.WARNING
    added_again = [h for h in root.handlers if h not in before]
    assert len(added_again) == 1
    assert added_again == _cli_handlers()
    for handler in before:
        assert handler in root.handlers
    assert foreign in root.handlers


def test_configure_logging_unknown_level_falls_back_to_info() -> None:
    """An unknown level name results in INFO."""
    configure_logging("NOT_A_LEVEL")

    assert logging.getLogger().level == logging.INFO


def test_configure_logging_handler_writes_to_current_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI handler writes log records to stderr."""
    configure_logging("INFO", "%(message)s")

    logging.getLogger(CLI_LOGGER).info("visible on stderr")

    assert "visible on stderr" in capsys.readouterr().err


def test_main_applies_config_log_level_and_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() reconfigures logging with config.log_level and config.log_format."""
    monkeypatch.setattr(
        scrape_strokeplay_data,
        "load_config",
        lambda: _dummy_config(log_level="DEBUG", log_format="%(message)s"),
    )
    monkeypatch.setattr(sys, "argv", ["scrape", "--list"])
    calls: list[tuple[str, str]] = []
    real_configure = scrape_strokeplay_data.configure_logging

    def _spy(level: str = "INFO", fmt: str = scrape_strokeplay_data.DEFAULT_LOG_FORMAT) -> None:
        calls.append((level, fmt))
        real_configure(level, fmt)

    monkeypatch.setattr(scrape_strokeplay_data, "configure_logging", _spy)

    main()

    assert calls[-1] == ("DEBUG", "%(message)s")
    assert logging.getLogger().level == logging.DEBUG
