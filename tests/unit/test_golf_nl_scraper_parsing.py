"""Tests for GolfNLScraper parsing with a mocked WebDriver.

The driver is a MagicMock whose page_source holds a synthetic fixture, so no browser
or network is used.
"""

from collections.abc import Callable
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from selenium.common.exceptions import WebDriverException

from pipelines.strokeplay.models import ScraperConfig
from pipelines.strokeplay.scrapers.golf_nl_parser import (
    parse_score_details_block,
    parse_scores_page,
)
from pipelines.strokeplay.scrapers.golf_nl_scraper import GolfNLScraper

LoadHtml = Callable[[str], str]

FAKE_EMAIL = "user@example.invalid"
FAKE_CREDENTIAL = "not-a-real-password"
FAKE_SCORES_URL = "https://example.invalid/scores"


@pytest.fixture
def scraper() -> GolfNLScraper:
    """A GolfNLScraper with fake config and no driver attached."""
    config = ScraperConfig(email=FAKE_EMAIL, password=FAKE_CREDENTIAL, scores_url=FAKE_SCORES_URL)
    return GolfNLScraper(config)


def _attach_driver(scraper: GolfNLScraper, page_source: str) -> MagicMock:
    driver = MagicMock()
    driver.page_source = page_source
    scraper.driver = driver
    return driver


def test_scrape_scores_parses_page_source(scraper: GolfNLScraper, golf_nl_html: LoadHtml) -> None:
    html = golf_nl_html("scores_page.html")
    driver = _attach_driver(scraper, html)

    with patch.object(scraper, "_wait_for_element") as wait:
        scores = scraper.scrape_scores()

    assert scores == parse_scores_page(html)
    assert len(scores) == 3
    driver.get.assert_called_once_with(FAKE_SCORES_URL)
    wait.assert_called_once()
    driver.find_elements.assert_not_called()


def test_scrape_scores_empty_page_returns_empty_list(
    scraper: GolfNLScraper, golf_nl_html: LoadHtml
) -> None:
    driver = _attach_driver(scraper, golf_nl_html("scores_page_empty.html"))

    with patch.object(scraper, "_wait_for_element"):
        scores = scraper.scrape_scores()

    assert scores == []
    driver.get.assert_called_once_with(FAKE_SCORES_URL)


def test_extract_score_details_matches_parser(
    scraper: GolfNLScraper, golf_nl_html: LoadHtml
) -> None:
    html = golf_nl_html("score_details_block.html")

    assert scraper._extract_score_details(html) == parse_score_details_block(html)


def test_scrape_scores_parse_error_fails_whole_call(
    scraper: GolfNLScraper, golf_nl_html: LoadHtml, caplog: pytest.LogCaptureFixture
) -> None:
    # Behaviour change in gsw-3sk.3: a parse error is no longer skipped per block;
    # it reaches the outer handler and the whole call returns [].
    _attach_driver(scraper, golf_nl_html("scores_page.html"))
    target = "pipelines.strokeplay.scrapers.golf_nl_scraper.parse_scores_page"

    with (
        patch.object(scraper, "_wait_for_element"),
        patch(target, side_effect=AttributeError("boom")),
    ):
        scores = scraper.scrape_scores()

    assert scores == []
    assert "Error scraping scores: boom" in caplog.text


def test_scrape_scores_page_source_error_returns_empty_list(scraper: GolfNLScraper) -> None:
    driver = MagicMock()
    type(driver).page_source = PropertyMock(side_effect=WebDriverException("gone"))
    scraper.driver = driver

    with patch.object(scraper, "_wait_for_element"):
        scores = scraper.scrape_scores()

    assert scores == []


def test_extract_score_details_error_returns_empty_dict(scraper: GolfNLScraper) -> None:
    target = "pipelines.strokeplay.scrapers.golf_nl_scraper.parse_score_details_block"

    with patch(target, side_effect=ValueError("bad")):
        assert scraper._extract_score_details("<div></div>") == {}
