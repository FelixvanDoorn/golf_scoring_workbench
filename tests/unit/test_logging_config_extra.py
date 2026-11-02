"""Extra tester checks for gsw-e9v: repeated main(), caplog, duplicate output and stderr errors.

No network, browser, real .env or database: load_config is patched to return a ScraperConfig
built with dummy credentials.
"""

import logging
import sys
from collections.abc import Iterator

import pytest

from pipelines.strokeplay import scrape_strokeplay_data
from pipelines.strokeplay.models import ScraperConfig
from pipelines.strokeplay.scrape_strokeplay_data import configure_logging, main
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


def _stream_handlers_on_root() -> list[logging.Handler]:
    # pytest's own capture handlers are not plain StreamHandlers writing to stderr.
    return [
        h
        for h in logging.getLogger().handlers
        if type(h) is logging.StreamHandler and h is scrape_strokeplay_data._cli_handler
    ]


def test_main_twice_does_not_stack_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two main() runs in one process leave exactly one CLI handler and no extra root handlers."""
    monkeypatch.setattr(scrape_strokeplay_data, "load_config", lambda: _dummy_config())
    monkeypatch.setattr(sys, "argv", ["scrape", "--list"])
    root = logging.getLogger()
    before = list(root.handlers)

    main()
    after_first = list(root.handlers)
    main()
    after_second = list(root.handlers)

    assert len(after_first) == len(before) + 1
    assert len(after_second) == len(before) + 1
    assert len(_stream_handlers_on_root()) == 1
    for handler in before:
        assert handler in after_second
    assert logging.getLogger(CLI_LOGGER).handlers == []
    assert logging.getLogger(SCRAPER_LOGGER).handlers == []


def test_main_twice_prints_log_line_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """After two main() runs, one log call produces exactly one stderr line (no duplicates)."""
    monkeypatch.setattr(
        scrape_strokeplay_data, "load_config", lambda: _dummy_config(log_format="%(message)s")
    )
    monkeypatch.setattr(sys, "argv", ["scrape", "--list"])
    main()
    main()
    capsys.readouterr()

    logging.getLogger(SCRAPER_LOGGER).warning("single-line-marker")

    assert capsys.readouterr().err.count("single-line-marker") == 1


def test_caplog_still_captures_after_configure_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """configure_logging does not remove pytest's caplog handler."""
    configure_logging("DEBUG", "%(message)s")
    configure_logging("INFO", "%(message)s")

    logging.getLogger(SCRAPER_LOGGER).info("seen-by-caplog")

    assert caplog.handler in logging.getLogger().handlers
    assert any(r.getMessage() == "seen-by-caplog" for r in caplog.records)


def test_caplog_still_captures_after_main(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Records logged after main() reconfigures logging still reach caplog."""
    monkeypatch.setattr(scrape_strokeplay_data, "load_config", lambda: _dummy_config())
    monkeypatch.setattr(sys, "argv", ["scrape", "--list"])
    main()

    logging.getLogger(CLI_LOGGER).warning("after-main")

    assert any(r.getMessage() == "after-main" for r in caplog.records)


def test_unknown_level_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """An unknown level name falls back to INFO and emits a warning naming the bad level."""
    configure_logging("NOT_A_LEVEL")

    assert logging.getLogger().level == logging.INFO
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("NOT_A_LEVEL" in r.getMessage() for r in warnings)


def test_lowercase_level_is_accepted() -> None:
    """Level names are case-insensitive, as config.yaml may use 'debug'."""
    configure_logging("debug")

    assert logging.getLogger().level == logging.DEBUG


def test_scraper_debug_check_follows_root_level() -> None:
    """The scraper logger's isEnabledFor(DEBUG) tracks the level set by configure_logging."""
    scraper = GolfNLScraper(_dummy_config(log_level="DEBUG"))

    configure_logging("INFO")
    assert scraper.logger.isEnabledFor(logging.DEBUG) is False
    assert scraper.logger.level == logging.NOTSET

    configure_logging("DEBUG")
    assert scraper.logger.isEnabledFor(logging.DEBUG) is True


def test_missing_config_error_on_stderr_once_and_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing config file is reported once on stderr in the default format, and exit is 1."""

    def _missing_config() -> None:
        raise FileNotFoundError("config.yaml not found here")

    monkeypatch.setattr(logging.root, "handlers", [])
    monkeypatch.setattr(scrape_strokeplay_data, "load_config", _missing_config)
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert err.count("config.yaml not found here") == 1
    assert f"{CLI_LOGGER} - ERROR - " in err
