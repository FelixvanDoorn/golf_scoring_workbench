"""Tests for error handling in pipelines.strokeplay.scrape_strokeplay_data.

load_config and GolfNLScraper are patched, so no config, .env, browser or network is used.
"""

import logging
import sys
from typing import Any

import pytest
from selenium.common.exceptions import WebDriverException

from pipelines.strokeplay import scrape_strokeplay_data
from pipelines.strokeplay.models import ScrapingResult
from pipelines.strokeplay.scrape_strokeplay_data import ScraperOrchestrator, main


def _fake_scraper_class(error: BaseException) -> type:
    """Build a fake scraper class whose run() raises the given error."""

    class FakeScraper:
        def __init__(self, config: Any) -> None:
            self.config = config

        def run(self) -> ScrapingResult:
            raise error

    return FakeScraper


@pytest.fixture
def patch_orchestrator(monkeypatch: pytest.MonkeyPatch):
    """Return a helper that patches load_config and GolfNLScraper for one error type."""

    def _patch(error: BaseException) -> None:
        monkeypatch.setattr(scrape_strokeplay_data, "load_config", lambda: object())
        monkeypatch.setattr(scrape_strokeplay_data, "GolfNLScraper", _fake_scraper_class(error))

    return _patch


def test_webdriver_error_becomes_failed_result(patch_orchestrator) -> None:
    """A WebDriverException from the scraper yields a failed ScrapingResult."""
    patch_orchestrator(WebDriverException("driver crashed"))
    orchestrator = ScraperOrchestrator()

    result = orchestrator.run_scraper("golf_nl")

    assert result.success is False
    assert result.score_details == []
    assert orchestrator.results["golf_nl"] is result
    assert "driver crashed" in orchestrator.results["golf_nl"].error_message


def test_programming_error_propagates(patch_orchestrator) -> None:
    """Unexpected errors such as RuntimeError are not swallowed by run_scraper."""
    patch_orchestrator(RuntimeError("bug"))
    orchestrator = ScraperOrchestrator()

    with pytest.raises(RuntimeError, match="bug"):
        orchestrator.run_scraper("golf_nl")

    assert "golf_nl" not in orchestrator.results


def test_main_exits_1_and_logs_error_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """main() logs an ERROR and exits with code 1 when config loading fails."""

    def _missing_config() -> None:
        raise FileNotFoundError("config.yaml not found")

    monkeypatch.setattr(scrape_strokeplay_data, "load_config", _missing_config)
    monkeypatch.setattr(sys, "argv", ["scrape_strokeplay_data"])

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records
    assert "config.yaml not found" in error_records[0].getMessage()
