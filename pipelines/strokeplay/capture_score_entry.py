"""Capture one golf.nl score entry as raw HTML for hand obfuscation.

This is a one-off tool the user runs locally with their own ``.env`` and browser:

    uv run python -m pipelines.strokeplay.capture_score_entry [--index N]

It logs in with ``GolfNLScraper``, opens the scores page, takes ONE
``div.c-linkBlock.c-score`` element (its outerHTML, plus the score details) and writes
it to ``data/captures/``, which is gitignored at the repository root and by a ``*``
``.gitignore`` the tool writes into the folder itself.

Privacy rules: the captured HTML holds personal data. It is never logged or printed,
and neither are the page URL, page source, email or password. Log messages hold only
the output path, byte count, capture mode, index and counts.

Workflow after a capture: the user obfuscates names, marker, course, dates,
member/NGF numbers and hrefs in the file by hand, copies the result to
``tests/fixtures/golf_nl/real_score_entry.html`` and confirms on the confirmation bead.
Only then is the file used as a test fixture or label source. Agents never read
``data/captures/``.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from pipelines.strokeplay.config_manager import load_config
from pipelines.strokeplay.scrapers.golf_nl_scraper import GolfNLScraper

logger = logging.getLogger(__name__)

ENTRY_SELECTOR = "div.c-linkBlock.c-score"
DETAILS_SELECTOR = "div.c-score__details"
DETAILS_CLASS = "c-score__details"
OUTSIDE_SEPARATOR = "<!-- details found outside the c-linkBlock entry -->"

# repo root / data / captures. Not data/raw/, which is tracked.
CAPTURE_DIR: Path = Path(__file__).resolve().parents[2] / "data" / "captures"

CaptureMode = Literal["inline", "expanded", "outside", "missing"]


class EntryNotFoundError(LookupError):
    """Raised when no score entry exists at the requested index."""


@dataclass(frozen=True)
class CapturedEntry:
    """One captured score entry.

    Attributes:
        entry_html: outerHTML of the ``div.c-linkBlock.c-score`` element.
        details_html: outerHTML of a details block found outside the entry. Set only
            in ``outside`` mode.
        mode: How the score details were found.
    """

    entry_html: str
    details_html: str | None
    mode: CaptureMode


def _has_details(html: str) -> bool:
    """Return True if html holds an element with the score details class."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.find(class_=DETAILS_CLASS) is not None


def _outer_html(element: WebElement) -> str:
    """Return the element's outerHTML, or an empty string if it has none."""
    return element.get_attribute("outerHTML") or ""


def extract_score_entry(driver: WebDriver, index: int = 0, timeout: float = 10) -> CapturedEntry:
    """Extract one score entry and make sure its score details are captured.

    Tries, in order: details already inside the entry (``inline``); details inside the
    entry after clicking it (``expanded``); details elsewhere on the page
    (``outside``). If none are found the entry is still returned (``missing``).

    Args:
        driver: A WebDriver that is already on the scores page.
        index: Zero-based index of the entry to capture.
        timeout: Seconds to wait for details to appear after clicking.

    Returns:
        The captured entry.

    Raises:
        EntryNotFoundError: If there is no entry at ``index``.
    """
    entries = driver.find_elements(By.CSS_SELECTOR, ENTRY_SELECTOR)
    if not 0 <= index < len(entries):
        raise EntryNotFoundError(
            f"Found {len(entries)} score entries; index {index} is out of range"
        )
    element = entries[index]

    # Read before any click: a click may navigate away or re-render the element.
    entry_html = _outer_html(element)
    if _has_details(entry_html):
        return CapturedEntry(entry_html=entry_html, details_html=None, mode="inline")

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", element)
    element.click()
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, DETAILS_SELECTOR))
        )
    except TimeoutException:
        logger.info("No score details appeared within %s seconds after the click", timeout)

    try:
        expanded_html = _outer_html(element)
    except StaleElementReferenceException:
        logger.info("Entry went stale after the click; keeping the pre-click HTML")
    else:
        if _has_details(expanded_html):
            return CapturedEntry(entry_html=expanded_html, details_html=None, mode="expanded")

    details = driver.find_elements(By.CSS_SELECTOR, DETAILS_SELECTOR)
    if details:
        logger.info("Found %d details blocks outside the entry; taking the first", len(details))
        return CapturedEntry(
            entry_html=entry_html, details_html=_outer_html(details[0]), mode="outside"
        )

    logger.warning("No score details found for entry %d; writing the entry only", index)
    return CapturedEntry(entry_html=entry_html, details_html=None, mode="missing")


def render_capture(entry: CapturedEntry, captured_at: datetime) -> str:
    """Render a captured entry as an HTML document with a warning header.

    The output holds only the header and the captured HTML: no URL, page title,
    cookies or config values.

    Args:
        entry: The captured entry.
        captured_at: When the capture was taken.

    Returns:
        The file content to write.
    """
    header = (
        "<!-- RAW golf.nl capture (gsw-7e0). UNSANITIZED: contains personal data. "
        "Obfuscate by hand before any use. "
        f"mode={entry.mode} captured_at={captured_at.isoformat()} -->"
    )
    parts = [header, entry.entry_html]
    if entry.details_html is not None:
        parts.extend([OUTSIDE_SEPARATOR, entry.details_html])
    return "\n".join(parts) + "\n"


def write_capture(content: str, capture_dir: Path, now: datetime) -> Path:
    """Write a capture to a new file in capture_dir and return its path.

    Also writes a ``*`` ``.gitignore`` into capture_dir if it is missing, so the
    folder stays ignored even if the root ``.gitignore`` changes.

    Args:
        content: The rendered capture.
        capture_dir: Directory to write into; created if needed.
        now: Timestamp used in the file name.

    Returns:
        Path of the written file.

    Raises:
        FileExistsError: If a capture with the same timestamp already exists. It is
            never overwritten, since it may already be hand-obfuscated.
    """
    capture_dir.mkdir(parents=True, exist_ok=True)
    gitignore = capture_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")

    path = capture_dir / f"score_entry_{now:%Y%m%d-%H%M%S}.raw.html"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)
    return path


def main(argv: list[str] | None = None) -> int:
    """Run a capture: log in, extract one score entry and write it to CAPTURE_DIR.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        0 on success, 1 on failure, 2 if the entry was written without score details.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Capture one golf.nl score entry (div.c-linkBlock.c-score) to a gitignored "
            "raw HTML file under data/captures/. Obfuscate it by hand before any use."
        )
    )
    parser.add_argument(
        "--index", type=int, default=0, help="zero-based index of the entry (default 0)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    try:
        config = load_config()
    except (OSError, ValueError) as e:
        logger.error("Could not load configuration: %s", type(e).__name__)
        return 1

    scraper = GolfNLScraper(config)
    try:
        scraper.driver = scraper._setup_driver()
        login_result = scraper.login()
        if not login_result.success:
            logger.error("Login failed; no capture written")
            return 1

        scraper.driver.get(config.scores_url)
        scraper._wait_for_element(By.CSS_SELECTOR, ENTRY_SELECTOR)
        entry = extract_score_entry(scraper.driver, args.index, config.timeout)

        now = datetime.now()
        content = render_capture(entry, now)
        path = write_capture(content, CAPTURE_DIR, now)
        logger.info(
            "Wrote raw capture to %s (mode=%s, %d bytes). Obfuscate it by hand, then "
            "confirm on the confirmation bead before use.",
            path,
            entry.mode,
            len(content.encode("utf-8")),
        )
        return 2 if entry.mode == "missing" else 0
    except EntryNotFoundError as e:
        logger.error("Capture failed: %s", e)
        return 1
    except (WebDriverException, OSError) as e:
        # Only the type: driver messages can echo page state.
        logger.error("Capture failed: %s", type(e).__name__)
        return 1
    finally:
        if scraper.driver:
            scraper.driver.quit()


if __name__ == "__main__":
    sys.exit(main())
