"""HTML parsing for golf.nl score pages.

This module works on HTML strings only and does not depend on Selenium, so the
parsing can be tested offline against saved fixtures. The class names below are
the selectors golf.nl uses on the scores page.
"""

import logging

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

SCORES_CONTAINER_CLASS = "c-scores"
DETAILS_CLASS = "c-score__details"
ROW_CLASS = "c-score__details__content"
LABEL_CLASS = "c-score__details__label"
TEXT_CLASS = "c-score__details__text"


def _parse_details_element(details: Tag | BeautifulSoup) -> dict[str, str]:
    """Collect label -> text pairs from the rows inside a details element."""
    score_data: dict[str, str] = {}
    for row in details.find_all("div", class_=ROW_CLASS):
        label_div = row.find("div", class_=LABEL_CLASS)
        text_div = row.find("div", class_=TEXT_CLASS)
        if label_div is None or text_div is None:
            continue
        label = label_div.get_text(strip=True)
        if not label:
            continue
        # A repeated label overwrites the earlier value, matching the old scraper.
        score_data[label] = text_div.get_text(strip=True)
    return score_data


def parse_score_details_block(html: str) -> dict[str, str]:
    """Parse one score details block into a label -> value mapping.

    Args:
        html: HTML containing a ``div.c-score__details`` block, either as the root
            element or nested inside other markup. If no such div is present, the
            rows are looked up in the whole document.

    Returns:
        Mapping of the stripped label text to the stripped value text. Rows that
        lack a label or text div, or whose label is empty, are skipped. If a label
        repeats, the last value wins.
    """
    soup = BeautifulSoup(html, "html.parser")
    details = soup.find("div", class_=DETAILS_CLASS)
    return _parse_details_element(details if details is not None else soup)


def parse_scores_page(html: str) -> list[dict[str, str]]:
    """Parse every score details block on a scores page.

    Args:
        html: Full HTML of the golf.nl scores page.

    Returns:
        One label -> value mapping per ``div.c-score__details`` block, in document
        order. Blocks that yield no data are dropped with a warning. A page with no
        blocks returns an empty list.
    """
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all("div", class_=DETAILS_CLASS)
    logger.info("Found %d score detail blocks", len(blocks))

    scores: list[dict[str, str]] = []
    for index, block in enumerate(blocks, start=1):
        score_data = _parse_details_element(block)
        if not score_data:
            logger.warning("Score %d: no data extracted", index)
            continue
        logger.debug("Score %d: extracted %d fields - %s", index, len(score_data), list(score_data))
        scores.append(score_data)
    return scores
