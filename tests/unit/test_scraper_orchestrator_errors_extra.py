"""Extra edge-case tests for error handling in scrape_strokeplay_data (tester-added).

load_config and GolfNLScraper are patched, so no config, .env, browser or network is used.
"""

import logging
import sys
from typing import Any

import pytest

from pipelines.strokeplay import scrape_strokeplay_data
from pipelines.strokeplay.models import ScrapingResult
from pipelines.strokeplay.scrape_strokeplay_data import ScraperOrchestrator, main


def _fake_scraper_class(error: BaseException | None) -> type:
    """Build a fake scraper class whose run() raises error, or fails cleanly if None."""

    class FakeScraper:
        def __init__(self, config: Any) -> None:
            self.config = config

        def run(self) -> ScrapingResult:
            if error is not None:
                raise error
            return ScrapingResult(success=False, score_details=[], error_message="no data")

    return FakeScraper


def _patch(monkeypatch: pytest.MonkeyPatch, error: BaseException | None) -> None:
    monkeypatch.setattr(scrape_strokeplay_data, "load_config", lambda: object())
    monkeypatch.setattr(scrape_strokeplay_data, "GolfNLScraper", _fake_scraper_class(error))


@pytest.mark.parametrize("error", [ValueError("bad row"), OSError("disk full")])
def test_value_and_os_errors_become_failed_result(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, error: BaseException
) -> None:
    """ValueError and OSError are expected failures: failed result, traceback logged."""
    _patch(monkeypatch, error)
    orchestrator = ScraperOrchestrator()

    with caplog.at_level(logging.ERROR):
        result = orchestrator.run_scraper("golf_nl")

    assert result.success is False
    assert result.total_scores_found == 0
    assert result.error_message == str(error)
    assert result.timestamp
    assert orchestrator.results["golf_nl"] is result
    records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert records
    assert records[0].exc_info is not None


@pytest.mark.parametrize("error", [TypeError("t"), KeyError("k")])
def test_type_and_key_errors_propagate(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """Programming errors are not converted into a failed result."""
    _patch(monkeypatch, error)
    orchestrator = ScraperOrchestrator()

    with pytest.raises(type(error)):
        orchestrator.run_scraper("golf_nl")
    assert orchestrator.results == {}


def test_main_unknown_scraper_exits_1_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An unknown --scrapers name raises ValueError, which main reports and exits 1."""
    _patch(monkeypatch, None)
    monkeypatch.setattr(sys, "argv", ["prog", "--scrapers", "nope"])

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert any("nope" in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)


def test_main_failed_scraper_result_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """A WebDriver-style failure yields a failed result and main exits 1 (not a crash)."""
    from selenium.common.exceptions import WebDriverException

    _patch(monkeypatch, WebDriverException("driver crashed"))
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_runtime_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """main no longer swallows unexpected errors."""
    _patch(monkeypatch, RuntimeError("bug"))
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(RuntimeError, match="bug"):
        main()


def test_main_missing_config_error_visible_on_stderr_without_logging_setup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no handlers configured anywhere, the ERROR still reaches stderr and exit is 1.

    Config fails before _setup_logging runs, so logging.lastResort must print the message.
    """

    def _missing_config() -> None:
        raise FileNotFoundError("config.yaml not found here")

    module_logger = logging.getLogger(scrape_strokeplay_data.__name__)
    monkeypatch.setattr(logging.root, "handlers", [])
    monkeypatch.setattr(module_logger, "handlers", [])
    monkeypatch.setattr(scrape_strokeplay_data, "load_config", _missing_config)
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "config.yaml not found here" in capsys.readouterr().err


def test_iterating_sheet_dict_matches_keys() -> None:
    """db_creation's 'for year in df_xlsx' yields sheet names (keys), as '.keys()' did."""
    sheets = {"2023": 1, "Course Pars": 2, "2024": 3, "Stroke Indices": 4}

    assert [y for y in sheets if "20" in y] == ["2023", "2024"]
