"""HTML parsing for golf.nl score pages.

This module works on HTML strings only and does not depend on Selenium, so the
parsing can be tested offline against saved fixtures. The class names below are
the selectors golf.nl uses on the scores page.

There are two layers: the raw layer (``parse_score_details_block`` and
``parse_scores_page``) returns label -> text dicts for debugging and discovering
new labels, while the typed layer (``parse_score_entry`` and
``parse_score_entries``) builds strict ``ScoreDetails`` records and raises
``GolfNLParseError`` on any unexpected markup.
"""

import calendar
import logging
import re
from collections.abc import Callable
from datetime import MAXYEAR, MINYEAR, datetime

from bs4 import BeautifulSoup, Tag

from pipelines.strokeplay.models import ScoreDetails

logger = logging.getLogger(__name__)

SCORES_CONTAINER_CLASS = "c-scores"
DETAILS_CLASS = "c-score__details"
ROW_CLASS = "c-score__details__content"
LABEL_CLASS = "c-score__details__label"
TEXT_CLASS = "c-score__details__text"
ENTRY_CLASSES = ("c-linkBlock", "c-score")
SUBTITLE_CLASS = "c-linkBlock__subtitle"
TITLE_CLASS = "c-linkBlock__title"

_ENTRY_SELECTOR = "div." + ".".join(ENTRY_CLASSES)

LABEL_TO_FIELD: dict[str, str] = {
    "Tee": "tee",
    "Qualifying": "qualifying",
    "Wedstrijd": "tournament",
    "Comment": "comment",
    "Scorekaart": "score_card_link",
    "Baanhandicap": "course_handicap",
    "Stableford": "stableford",
    "Totaal aantal slagen": "total_strokes",
    "Aangepaste bruto score": "adjusted_gross_score",
    "Spelcondities (PCC)": "playing_conditions_correction",
    "Dagresultaat (SD)": "score_differential",
    "Handicap": "handicap",
    "Marker": "marker",
    "Ondertekend": "signed",
}
"""The 14 detail labels golf.nl shows, in page order, mapped to ScoreDetails fields."""

REQUIRED_LABELS: frozenset[str] = frozenset(
    {
        "Tee",
        "Qualifying",
        "Baanhandicap",
        "Stableford",
        "Totaal aantal slagen",
        "Aangepaste bruto score",
        "Spelcondities (PCC)",
        "Dagresultaat (SD)",
        "Handicap",
    }
)
"""Labels every entry must have. The other labels in LABEL_TO_FIELD are optional
(tracked by decision gsw-d0j) and yield ``None`` when absent."""

DUTCH_MONTHS: dict[str, int] = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}
"""Dutch month names. An explicit dict because locale availability differs per machine."""

_PLAYED_AT_PATTERN = re.compile(r"(\d{1,2}) ([a-z]+) (\d{4}) (\d{1,2}):(\d{2})")
_INT_PATTERN = re.compile(r"[+-]?[0-9]+")
_DECIMAL_PATTERN = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")


class GolfNLParseError(ValueError):
    """Raised when a golf.nl score entry does not match the expected markup.

    Messages hold labels, field names, header class names, counts and entry
    indexes only, never parsed values: markers, comments and clubs are personal
    data.
    """


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


def _collapse_whitespace(text: str) -> str:
    """Collapse every whitespace run (including non-breaking spaces) to one space."""
    return " ".join(text.split())


def _parse_bool(text: str, label: str) -> bool:
    """Parse a golf.nl Ja/Nee value."""
    value = text.strip().casefold()
    if value == "ja":
        return True
    if value == "nee":
        return False
    raise GolfNLParseError(f"{label!r}: not Ja or Nee")


def _parse_int(text: str, label: str, plus_is_negative: bool = False) -> int:
    """Parse an integer with an optional sign.

    With ``plus_is_negative`` a leading "+" marks a WHS plus handicap, which is
    stored as a negative number.
    """
    value = text.strip()
    if not _INT_PATTERN.fullmatch(value):
        raise GolfNLParseError(f"{label!r}: not an integer")
    number = int(value)
    if plus_is_negative and value.startswith("+"):
        return -number
    return number


def _parse_decimal(text: str, label: str, plus_is_negative: bool = False) -> float:
    """Parse a decimal written with a dot (golf.nl) or a single decimal comma.

    A value with both separators, or more than one separator, is rejected because
    it could contain a thousands separator.
    """
    value = text.strip()
    if value.count(",") + value.count(".") > 1:
        raise GolfNLParseError(f"{label!r}: more than one decimal separator")
    value = value.replace(",", ".")
    if not _DECIMAL_PATTERN.fullmatch(value):
        raise GolfNLParseError(f"{label!r}: not a decimal number")
    number = float(value)
    if plus_is_negative and value.startswith("+"):
        return -number
    return number


def _parse_played_at(text: str) -> datetime:
    """Parse a header date such as "1 januari 2000 09:00" into a naive datetime."""
    match = _PLAYED_AT_PATTERN.fullmatch(_collapse_whitespace(text))
    if match is None:
        raise GolfNLParseError(f"{SUBTITLE_CLASS}: expected '<day> <month> <year> <hh>:<mm>'")
    day, month_name, year, hour, minute = match.groups()
    month = DUTCH_MONTHS.get(month_name)
    if month is None:
        raise GolfNLParseError(f"{SUBTITLE_CLASS}: unknown Dutch month name")
    # Every datetime() constraint is checked here first, the year before
    # monthrange, so a bad header raises GolfNLParseError and never ValueError.
    if not MINYEAR <= int(year) <= MAXYEAR:
        raise GolfNLParseError(f"{SUBTITLE_CLASS}: date or time out of range")
    days_in_month = calendar.monthrange(int(year), month)[1]
    if not (1 <= int(day) <= days_in_month and int(hour) < 24 and int(minute) < 60):
        raise GolfNLParseError(f"{SUBTITLE_CLASS}: date or time out of range")
    return datetime(int(year), month, int(day), int(hour), int(minute))


def _text_of(element: Tag) -> str:
    """Return the whitespace-collapsed text of an element."""
    return _collapse_whitespace(element.get_text(" ", strip=True))


def _collect_text_divs(details: Tag) -> dict[str, Tag]:
    """Map each stripped detail label to its text div, failing on malformed rows.

    Unlike the raw layer, an empty label, a missing text div or a repeated label
    raises instead of being skipped or overwritten.
    """
    rows: dict[str, Tag] = {}
    for row in details.find_all("div", class_=ROW_CLASS):
        label_div = row.find("div", class_=LABEL_CLASS)
        label = _text_of(label_div) if isinstance(label_div, Tag) else ""
        if not label:
            raise GolfNLParseError("detail row without a label")
        text_div = row.find("div", class_=TEXT_CLASS)
        if not isinstance(text_div, Tag):
            raise GolfNLParseError(f"{label!r}: detail row without a text div")
        if label in rows:
            raise GolfNLParseError(f"{label!r}: duplicate detail label")
        rows[label] = text_div
    return rows


def _parse_score_card_link(text_div: Tag, label: str) -> str:
    """Return the href of the first link in the Scorekaart row, as-is."""
    link = text_div.find("a")
    href = link.get("href") if isinstance(link, Tag) else None
    if not isinstance(href, str) or not href.strip():
        raise GolfNLParseError(f"{label!r}: no link with an href")
    return href.strip()


_TEXT_CONVERTERS: dict[str, Callable[[str, str], object]] = {
    "tee": lambda text, label: text,
    "qualifying": _parse_bool,
    "tournament": _parse_bool,
    "comment": lambda text, label: text,
    "course_handicap": lambda text, label: _parse_int(text, label, plus_is_negative=True),
    "stableford": _parse_int,
    "total_strokes": _parse_int,
    "adjusted_gross_score": _parse_int,
    "playing_conditions_correction": _parse_int,
    "score_differential": _parse_decimal,
    "handicap": lambda text, label: _parse_decimal(text, label, plus_is_negative=True),
    "marker": lambda text, label: text,
    "signed": _parse_bool,
}
"""Converters for every field whose value comes from the row text (all but the link)."""

_OPTIONAL_STR_FIELDS = frozenset({"comment", "marker"})


def _header_text(entry: Tag, header_class: str) -> str:
    """Return the non-empty, whitespace-collapsed text of a header div."""
    header = entry.find("div", class_=header_class)
    text = _text_of(header) if isinstance(header, Tag) else ""
    if not text:
        raise GolfNLParseError(f"missing or empty header div.{header_class}")
    return text


def _single_entry(html: str) -> Tag:
    """Return the only score entry in an HTML string."""
    entries = BeautifulSoup(html, "html.parser").select(_ENTRY_SELECTOR)
    if len(entries) != 1:
        raise GolfNLParseError(
            f"expected exactly one {_ENTRY_SELECTOR} entry, found {len(entries)}"
        )
    return entries[0]


def _checked_entry(entry: Tag) -> Tag:
    """Return the element if it is a score entry, so a page or container is rejected."""
    classes = entry.get("class") or []
    if entry.name != "div" or not all(cls in classes for cls in ENTRY_CLASSES):
        raise GolfNLParseError(f"element is not a {_ENTRY_SELECTOR} entry")
    return entry


def parse_score_entry(entry: Tag | str) -> ScoreDetails:
    """Parse one golf.nl score entry into a typed ScoreDetails.

    Args:
        entry: The ``div.c-linkBlock.c-score`` element, or an HTML string that
            contains exactly one such element.

    Returns:
        The parsed entry. Optional labels that are absent, and empty optional
        text values, become ``None``.

    Raises:
        GolfNLParseError: If the element is not a score entry (or the string
            does not hold exactly one), the header or details block is missing, a detail
            row is malformed or duplicated, a label is unknown, a required label
            is missing or empty, or a value cannot be parsed.
    """
    element = _single_entry(entry) if isinstance(entry, str) else _checked_entry(entry)

    played_at = _parse_played_at(_header_text(element, SUBTITLE_CLASS))
    club_name = _header_text(element, TITLE_CLASS)

    details = element.find("div", class_=DETAILS_CLASS)
    if not isinstance(details, Tag):
        raise GolfNLParseError(f"entry without div.{DETAILS_CLASS}")
    rows = _collect_text_divs(details)

    unknown = sorted(label for label in rows if label not in LABEL_TO_FIELD)
    if unknown:
        raise GolfNLParseError(f"unknown detail labels: {unknown}")
    missing = sorted(REQUIRED_LABELS - rows.keys())
    if missing:
        raise GolfNLParseError(f"missing required detail labels: {missing}")

    values: dict[str, object] = dict.fromkeys(LABEL_TO_FIELD.values())
    for label, text_div in rows.items():
        field = LABEL_TO_FIELD[label]
        if field == "score_card_link":
            values[field] = _parse_score_card_link(text_div, label)
            continue
        text = _text_of(text_div)
        if not text:
            if field in _OPTIONAL_STR_FIELDS:
                continue
            raise GolfNLParseError(f"{label!r}: empty value")
        values[field] = _TEXT_CONVERTERS[field](text, label)

    logger.debug("Parsed score entry with %d detail rows", len(rows))
    return ScoreDetails(played_at=played_at, club_name=club_name, **values)


def parse_score_entries(html: str) -> list[ScoreDetails]:
    """Parse every score entry on a golf.nl scores page.

    Args:
        html: Full HTML of the golf.nl scores page.

    Returns:
        One ScoreDetails per ``div.c-linkBlock.c-score`` inside ``div.c-scores``,
        in document order. A container without entries returns an empty list.

    Raises:
        GolfNLParseError: If the page has no ``div.c-scores`` container, or any
            entry fails to parse. The message is prefixed with ``entry <n>: ``
            (1-based); no partial results are returned.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_=SCORES_CONTAINER_CLASS)
    if not isinstance(container, Tag):
        raise GolfNLParseError(
            f"no div.{SCORES_CONTAINER_CLASS} container: wrong page or changed markup"
        )

    entries = container.select(_ENTRY_SELECTOR)
    logger.info("Found %d score entries", len(entries))
    scores: list[ScoreDetails] = []
    for index, entry in enumerate(entries, start=1):
        try:
            scores.append(parse_score_entry(entry))
        except GolfNLParseError as err:
            raise GolfNLParseError(f"entry {index}: {err}") from err
    return scores
