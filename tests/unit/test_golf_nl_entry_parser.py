"""Offline tests for the typed layer of pipelines.strokeplay.scrapers.golf_nl_parser.

Input comes from the sanitized real entry and synthetic fixtures under
tests/fixtures/golf_nl, edited inline per test where a malformed entry is needed.
"""

import dataclasses
import logging
import re
from collections.abc import Callable
from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from pipelines.strokeplay.models import ScoreDetails
from pipelines.strokeplay.scrapers import golf_nl_parser
from pipelines.strokeplay.scrapers.golf_nl_parser import (
    DUTCH_MONTHS,
    LABEL_TO_FIELD,
    REQUIRED_LABELS,
    GolfNLParseError,
    parse_score_details_block,
    parse_score_entries,
    parse_score_entry,
)

LoadHtml = Callable[[str], str]

REAL_ENTRY = "real_score_entry.html"
ENTRIES_PAGE = "scores_page_entries.html"

EXPECTED_REAL = ScoreDetails(
    played_at=datetime(2000, 1, 1, 9, 0),
    club_name="Voorbeeld Golfclub",
    tee="Wit",
    qualifying=True,
    tournament=True,
    comment="Wedstrijd #0000: Naam Wedstrijd",
    score_card_link="/mijn-spel/scores/scorekaart-bekijken?scorecardid=AAAAAAAA",
    course_handicap=18,
    stableford=36,
    total_strokes=88,
    adjusted_gross_score=88,
    playing_conditions_correction=0,
    score_differential=12.3,
    handicap=14.2,
    marker="Piet Patat",
    signed=True,
)

EXPECTED_FIELDS = [
    ("played_at", datetime),
    ("club_name", str),
    ("tee", str),
    ("qualifying", bool),
    ("tournament", bool | None),
    ("comment", str | None),
    ("score_card_link", str | None),
    ("course_handicap", int),
    ("stableford", int),
    ("total_strokes", int),
    ("adjusted_gross_score", int),
    ("playing_conditions_correction", int),
    ("score_differential", float),
    ("handicap", float),
    ("marker", str | None),
    ("signed", bool | None),
]

REAL_LABELS = [
    "Tee",
    "Qualifying",
    "Wedstrijd",
    "Comment",
    "Scorekaart",
    "Baanhandicap",
    "Stableford",
    "Totaal aantal slagen",
    "Aangepaste bruto score",
    "Spelcondities (PCC)",
    "Dagresultaat (SD)",
    "Handicap",
    "Marker",
    "Ondertekend",
]


def _edit(html: str, old: str, new: str) -> str:
    """Replace exactly one occurrence of ``old``, failing loudly if it is not unique."""
    assert html.count(old) == 1, old
    return html.replace(old, new)


def _set_value(html: str, label: str, value: str) -> str:
    """Replace the value of a simple single-line detail row in the real entry."""
    pattern = re.compile(
        rf'(<div class="c-score__details__label">{re.escape(label)}</div>\s*'
        r'<div class="c-score__details__text">)[^<]*(</div>)'
    )
    edited, count = pattern.subn(rf"\g<1>{value}\g<2>", html)
    assert count == 1, label
    return edited


def _remove_row(html: str, label: str) -> str:
    """Remove the detail row with the given label from an entry."""
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("div", class_="c-score__details__content"):
        if row.find("div", class_="c-score__details__label").get_text(strip=True) == label:
            row.decompose()
            return str(soup)
    raise AssertionError(label)


def _page(*entries: str) -> str:
    """Wrap entries in a minimal scores page."""
    return f'<html><body><div class="c-scores">{"".join(entries)}</div></body></html>'


# --- model -------------------------------------------------------------------


def test_score_details_fields_in_order() -> None:
    fields = [(f.name, f.type) for f in dataclasses.fields(ScoreDetails)]
    assert fields == EXPECTED_FIELDS


def test_score_details_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        EXPECTED_REAL.tee = "Geel"  # type: ignore[misc]


def test_label_mapping_and_required_labels() -> None:
    assert list(LABEL_TO_FIELD) == REAL_LABELS
    assert set(LABEL_TO_FIELD.values()) == {name for name, _ in EXPECTED_FIELDS[2:]}
    assert set(LABEL_TO_FIELD) > REQUIRED_LABELS
    assert set(LABEL_TO_FIELD) - REQUIRED_LABELS == {
        "Wedstrijd",
        "Comment",
        "Scorekaart",
        "Marker",
        "Ondertekend",
    }
    assert issubclass(GolfNLParseError, ValueError)


# --- happy paths ---------------------------------------------------------------


def test_parse_real_entry_from_string(golf_nl_html: LoadHtml) -> None:
    assert parse_score_entry(golf_nl_html(REAL_ENTRY)) == EXPECTED_REAL


def test_parse_real_entry_from_tag(golf_nl_html: LoadHtml) -> None:
    soup = BeautifulSoup(golf_nl_html(REAL_ENTRY), "html.parser")
    entry = soup.select_one("div.c-linkBlock.c-score")
    assert entry is not None
    assert parse_score_entry(entry) == EXPECTED_REAL


def test_parse_entries_page(golf_nl_html: LoadHtml) -> None:
    first, second, third = parse_score_entries(golf_nl_html(ENTRIES_PAGE))

    assert first == EXPECTED_REAL

    assert second.played_at == datetime(2000, 3, 15, 14, 5)
    assert second.club_name == "Andere Golfclub"
    assert second.qualifying is False
    assert second.tournament is False
    assert second.signed is False
    assert second.playing_conditions_correction == 1
    assert second.score_differential == -1.5
    assert second.handicap == -2.4
    assert second.course_handicap == -3
    assert second.score_card_link.endswith("scorecardid=BBBBBBBB")

    assert third.played_at == datetime(2000, 12, 31, 8, 30)
    assert third.club_name == "Derde Golfclub"
    assert third.tournament is None
    assert third.comment is None
    assert third.score_card_link.endswith("scorecardid=CCCCCCCC")


def test_empty_scores_page_returns_empty_list(golf_nl_html: LoadHtml) -> None:
    assert parse_score_entries(golf_nl_html("scores_page_empty.html")) == []


def test_entries_fixture_shape(golf_nl_html: LoadHtml) -> None:
    html = golf_nl_html(ENTRIES_PAGE)
    assert html.splitlines()[0] == (
        "<!-- SYNTHETIC fixture modelled on tests/fixtures/golf_nl/real_score_entry.html "
        "(real golf.nl structure and labels); contains no real personal data -->"
    )
    assert "@" not in html
    assert re.search(r"https?://", html) is None
    assert re.search(r"[0-9]{5,}", html) is None

    entries = BeautifulSoup(html, "html.parser").select("div.c-scores div.c-linkBlock.c-score")
    row_counts = [len(parse_score_details_block(str(entry))) for entry in entries]
    assert row_counts == [14, 14, 12]


def test_missing_optional_labels_give_none(golf_nl_html: LoadHtml) -> None:
    html = golf_nl_html(REAL_ENTRY)
    for label in ("Scorekaart", "Marker", "Ondertekend"):
        html = _remove_row(html, label)
    details = parse_score_entry(html)
    assert details.score_card_link is None
    assert details.marker is None
    assert details.signed is None


def test_empty_optional_text_gives_none(golf_nl_html: LoadHtml) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), "Comment", "  ")
    assert parse_score_entry(html).comment is None


# --- value parsing -------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "raw", "field", "expected"),
    [
        ("Dagresultaat (SD)", "12.3", "score_differential", 12.3),
        ("Dagresultaat (SD)", "12,3", "score_differential", 12.3),
        ("Dagresultaat (SD)", " 14.2 ", "score_differential", 14.2),
        ("Dagresultaat (SD)", "-1.5", "score_differential", -1.5),
        ("Dagresultaat (SD)", "+1.5", "score_differential", 1.5),
        ("Dagresultaat (SD)", "7", "score_differential", 7.0),
        ("Spelcondities (PCC)", "+1", "playing_conditions_correction", 1),
        ("Spelcondities (PCC)", "-1", "playing_conditions_correction", -1),
        ("Baanhandicap", "+3", "course_handicap", -3),
        ("Baanhandicap", "54", "course_handicap", 54),
        ("Stableford", " 40 ", "stableford", 40),
        ("Qualifying", "ja", "qualifying", True),
        ("Qualifying", "Ja", "qualifying", True),
        ("Qualifying", "NEE", "qualifying", False),
        ("Ondertekend", "nee", "signed", False),
        ("Wedstrijd", "JA", "tournament", True),
    ],
)
def test_value_parsing(
    golf_nl_html: LoadHtml, label: str, raw: str, field: str, expected: object
) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), label, raw)
    assert getattr(parse_score_entry(html), field) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("14.2", 14.2), ("14,2", 14.2), ("+2.4", -2.4), ("+0,5", -0.5), ("-1.0", -1.0)],
)
def test_handicap_plus_is_negative(golf_nl_html: LoadHtml, raw: str, expected: float) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "\n                14.2 </div>", f"{raw}</div>")
    assert parse_score_entry(html).handicap == expected


@pytest.mark.parametrize(("month_name", "month"), list(DUTCH_MONTHS.items()))
def test_dutch_month_names(golf_nl_html: LoadHtml, month_name: str, month: int) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", f"9 {month_name} 2001 17:45")
    assert parse_score_entry(html).played_at == datetime(2001, month, 9, 17, 45)


def test_dutch_months_cover_the_year() -> None:
    assert sorted(DUTCH_MONTHS.values()) == list(range(1, 13))


def test_played_at_collapses_non_breaking_spaces(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", "1&nbsp;januari  2000\n09:00")
    assert parse_score_entry(html).played_at == datetime(2000, 1, 1, 9, 0)


# --- errors --------------------------------------------------------------------


def test_unknown_label(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), ">Tee<", ">Teebox<")
    with pytest.raises(GolfNLParseError, match="Teebox"):
        parse_score_entry(html)


def test_two_unknown_labels_are_both_named(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), ">Tee<", ">Teebox<")
    html = _edit(html, ">Stableford<", ">Punten<")
    with pytest.raises(GolfNLParseError, match=r"Punten.*Teebox"):
        parse_score_entry(html)


def test_missing_required_label(golf_nl_html: LoadHtml) -> None:
    html = _remove_row(golf_nl_html(REAL_ENTRY), "Stableford")
    with pytest.raises(GolfNLParseError, match="missing required.*Stableford"):
        parse_score_entry(html)


def test_duplicate_label(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), ">Wedstrijd<", ">Qualifying<")
    with pytest.raises(GolfNLParseError, match="Qualifying.*duplicate"):
        parse_score_entry(html)


def test_empty_label_row(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), ">Tee<", "> <")
    with pytest.raises(GolfNLParseError, match="without a label"):
        parse_score_entry(html)


def test_row_without_text_div(golf_nl_html: LoadHtml) -> None:
    html = _edit(
        golf_nl_html(REAL_ENTRY),
        '<div class="c-score__details__text">Wit</div>',
        "<span>Wit</span>",
    )
    with pytest.raises(GolfNLParseError, match="Tee.*without a text div"):
        parse_score_entry(html)


def test_empty_required_value(golf_nl_html: LoadHtml) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), "Tee", "")
    with pytest.raises(GolfNLParseError, match="Tee.*empty value"):
        parse_score_entry(html)


@pytest.mark.parametrize(
    ("label", "raw", "message"),
    [
        ("Stableford", "abc", "Stableford.*not an integer"),
        ("Stableford", "12.0", "Stableford.*not an integer"),
        ("Baanhandicap", "++3", "Baanhandicap.*not an integer"),
        ("Dagresultaat (SD)", "1.234,5", r"Dagresultaat \(SD\).*more than one decimal separator"),
        ("Dagresultaat (SD)", "1,234,5", r"Dagresultaat \(SD\).*more than one decimal separator"),
        ("Dagresultaat (SD)", "12.", r"Dagresultaat \(SD\).*not a decimal"),
        ("Dagresultaat (SD)", "abc", r"Dagresultaat \(SD\).*not a decimal"),
        ("Qualifying", "Misschien", "Qualifying.*not Ja or Nee"),
        ("Ondertekend", "yes", "Ondertekend.*not Ja or Nee"),
    ],
)
def test_unparseable_values(golf_nl_html: LoadHtml, label: str, raw: str, message: str) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), label, raw)
    with pytest.raises(GolfNLParseError, match=message):
        parse_score_entry(html)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("2000-01-01 09:00", "expected '<day> <month> <year>"),
        ("1 januari 2000", "expected '<day> <month> <year>"),
        ("1 Januari 2000 09:00", "expected '<day> <month> <year>"),
        ("1 janvier 2000 09:00", "unknown Dutch month"),
        ("31 februari 2000 09:00", "out of range"),
        ("1 januari 2000 25:00", "out of range"),
    ],
)
def test_unparseable_played_at(golf_nl_html: LoadHtml, raw: str, message: str) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", raw)
    with pytest.raises(GolfNLParseError, match=message):
        parse_score_entry(html)


@pytest.mark.parametrize(
    ("old", "header_class"),
    [
        ('<div class="c-linkBlock__subtitle">1 januari 2000 09:00</div>', "c-linkBlock__subtitle"),
        ("1 januari 2000 09:00", "c-linkBlock__subtitle"),
        ("Voorbeeld Golfclub", "c-linkBlock__title"),
    ],
    ids=["subtitle-removed", "subtitle-empty", "title-empty"],
)
def test_missing_header(golf_nl_html: LoadHtml, old: str, header_class: str) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), old, "")
    with pytest.raises(GolfNLParseError, match=f"header div.{header_class}"):
        parse_score_entry(html)


def test_missing_title_div(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), 'class="c-linkBlock__title"', 'class="other"')
    with pytest.raises(GolfNLParseError, match="header div.c-linkBlock__title"):
        parse_score_entry(html)


def test_entry_without_details(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), 'class="c-score__details"', 'class="other"')
    with pytest.raises(GolfNLParseError, match=r"without div\.c-score__details"):
        parse_score_entry(html)


def test_score_card_row_without_link(golf_nl_html: LoadHtml) -> None:
    html = _edit(
        golf_nl_html(REAL_ENTRY),
        '<a href="/mijn-spel/scores/scorekaart-bekijken?scorecardid=AAAAAAAA">',
        "<a>",
    )
    with pytest.raises(GolfNLParseError, match="Scorekaart.*no link with an href"):
        parse_score_entry(html)


def test_page_without_scores_container(golf_nl_html: LoadHtml) -> None:
    html = f"<html><body>{golf_nl_html(REAL_ENTRY)}</body></html>"
    with pytest.raises(GolfNLParseError, match=r"no div\.c-scores container"):
        parse_score_entries(html)


def test_error_in_second_entry_is_prefixed(golf_nl_html: LoadHtml) -> None:
    good = golf_nl_html(REAL_ENTRY)
    bad = _set_value(good, "Stableford", "abc")
    with pytest.raises(GolfNLParseError, match=r"^entry 2: 'Stableford'") as excinfo:
        parse_score_entries(_page(good, bad, good))
    assert isinstance(excinfo.value.__cause__, GolfNLParseError)


@pytest.mark.parametrize(("count", "found"), [(0, "found 0"), (2, "found 2")])
def test_string_with_zero_or_two_entries(golf_nl_html: LoadHtml, count: int, found: str) -> None:
    html = "<div>" + golf_nl_html(REAL_ENTRY) * count + "</div>"
    with pytest.raises(GolfNLParseError, match=f"exactly one .*{found}"):
        parse_score_entry(html)


def test_legacy_synthetic_labels_are_unknown(golf_nl_html: LoadHtml) -> None:
    soup = BeautifulSoup(golf_nl_html("scores_page.html"), "html.parser")
    details = soup.find("div", class_="c-score__details")
    entry = (
        '<div class="c-linkBlock c-score">'
        '<div class="c-linkBlock__subtitle">1 januari 2000 09:00</div>'
        '<div class="c-linkBlock__title">Voorbeeld Golfclub</div>'
        f"{details}</div>"
    )
    with pytest.raises(
        GolfNLParseError, match=r"unknown detail labels: \['Datum', 'Score differential'\]"
    ):
        parse_score_entry(entry)


# --- privacy -------------------------------------------------------------------

SENTINEL = "SENTINEL-PERSONAL-DATA"


def test_error_and_logs_hold_no_values(
    golf_nl_html: LoadHtml, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=golf_nl_parser.__name__)
    html = _edit(golf_nl_html(REAL_ENTRY), "Piet Patat", SENTINEL)
    bad = _set_value(html, "Stableford", "x")

    with pytest.raises(GolfNLParseError) as excinfo:
        parse_score_entry(bad)
    message = str(excinfo.value)
    assert SENTINEL not in message
    assert "'x'" not in message

    with pytest.raises(GolfNLParseError) as page_excinfo:
        parse_score_entries(_page(html, bad))
    assert SENTINEL not in str(page_excinfo.value)

    assert parse_score_entries(_page(html))[0].marker == SENTINEL
    assert parse_score_entry(html).marker == SENTINEL
    assert SENTINEL not in caplog.text
    assert caplog.records, "expected the parser to log at least one record"


# --- tester additions ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("29 februari 2000 09:00", datetime(2000, 2, 29, 9, 0)),
        ("31 december 2000 23:59", datetime(2000, 12, 31, 23, 59)),
        ("1 januari 2000 00:00", datetime(2000, 1, 1, 0, 0)),
        ("01 januari 2000 9:05", datetime(2000, 1, 1, 9, 5)),
    ],
)
def test_played_at_boundaries_accepted(
    golf_nl_html: LoadHtml, raw: str, expected: datetime
) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", raw)
    assert parse_score_entry(html).played_at == expected


@pytest.mark.parametrize(
    "raw",
    [
        "29 februari 2001 09:00",
        "31 april 2000 09:00",
        "0 januari 2000 09:00",
        "32 januari 2000 09:00",
        "1 januari 2000 24:00",
        "1 januari 2000 09:60",
    ],
)
def test_played_at_out_of_range_rejected(golf_nl_html: LoadHtml, raw: str) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", raw)
    with pytest.raises(GolfNLParseError, match="out of range"):
        parse_score_entry(html)


def test_year_zero_raises_parse_error(golf_nl_html: LoadHtml) -> None:
    html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", "1 januari 0000 09:00")
    with pytest.raises(GolfNLParseError, match="out of range"):
        parse_score_entry(html)


@pytest.mark.parametrize("selector", [None, "div.c-scores"], ids=["whole-page", "scores-container"])
def test_tag_that_is_not_an_entry_raises(golf_nl_html: LoadHtml, selector: str | None) -> None:
    soup = BeautifulSoup(golf_nl_html(ENTRIES_PAGE), "html.parser")
    element = soup if selector is None else soup.select_one(selector)
    assert element is not None
    with pytest.raises(GolfNLParseError, match="is not a div.c-linkBlock.c-score entry"):
        parse_score_entry(element)


@pytest.mark.parametrize("label", ["Wedstrijd", "Ondertekend"])
def test_empty_optional_boolean_raises(golf_nl_html: LoadHtml, label: str) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), label, " ")
    with pytest.raises(GolfNLParseError, match=f"{label}.*empty value"):
        parse_score_entry(html)


@pytest.mark.parametrize(
    ("label", "raw", "field"),
    [
        ("Baanhandicap", "-3", "course_handicap"),
        ("Baanhandicap", "+3", "course_handicap"),
    ],
)
def test_course_handicap_signs_both_mean_plus(
    golf_nl_html: LoadHtml, label: str, raw: str, field: str
) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), label, raw)
    assert getattr(parse_score_entry(html), field) == -3


VALUE_SENTINEL = "SENTINEL9VALUE"


@pytest.mark.parametrize(
    ("label", "raw"),
    [
        ("Stableford", VALUE_SENTINEL),
        ("Baanhandicap", VALUE_SENTINEL),
        ("Dagresultaat (SD)", VALUE_SENTINEL),
        ("Dagresultaat (SD)", f"1,2.{VALUE_SENTINEL}"),
        ("Qualifying", VALUE_SENTINEL),
        ("Ondertekend", VALUE_SENTINEL),
    ],
)
def test_value_errors_never_echo_the_value(golf_nl_html: LoadHtml, label: str, raw: str) -> None:
    html = _set_value(golf_nl_html(REAL_ENTRY), label, raw)
    with pytest.raises(GolfNLParseError) as excinfo:
        parse_score_entries(_page(html))
    assert str(excinfo.value).startswith("entry 1: ")
    assert VALUE_SENTINEL not in str(excinfo.value)


def test_date_errors_never_echo_the_value(golf_nl_html: LoadHtml) -> None:
    for raw in (f"1 {VALUE_SENTINEL.lower()} 2000 09:00", f"{VALUE_SENTINEL} 2000"):
        html = _edit(golf_nl_html(REAL_ENTRY), "1 januari 2000 09:00", raw)
        with pytest.raises(GolfNLParseError) as excinfo:
            parse_score_entry(html)
        assert VALUE_SENTINEL.lower() not in str(excinfo.value).lower()


def test_unknown_label_error_holds_no_row_value(golf_nl_html: LoadHtml) -> None:
    html = _edit(
        golf_nl_html(REAL_ENTRY),
        'details__label">Marker<',
        'details__label">Begeleider<',
    )
    html = _edit(html, "Piet Patat", SENTINEL)
    with pytest.raises(GolfNLParseError, match="Begeleider") as excinfo:
        parse_score_entry(html)
    assert SENTINEL not in str(excinfo.value)


def test_entry_with_empty_details_reports_all_required_missing(golf_nl_html: LoadHtml) -> None:
    entry = (
        '<div class="c-linkBlock c-score">'
        '<div class="c-linkBlock__subtitle">1 januari 2000 09:00</div>'
        '<div class="c-linkBlock__title">Voorbeeld Golfclub</div>'
        '<div class="c-score__details"></div></div>'
    )
    with pytest.raises(GolfNLParseError) as excinfo:
        parse_score_entry(entry)
    message = str(excinfo.value)
    assert message.startswith("missing required detail labels")
    assert all(label in message for label in REQUIRED_LABELS)


def test_entries_outside_container_are_ignored(golf_nl_html: LoadHtml) -> None:
    real = golf_nl_html(REAL_ENTRY)
    stray = _edit(real, "Voorbeeld Golfclub", "Buiten Golfclub")
    html = f'<html><body>{stray}<div class="c-scores">{real}</div></body></html>'
    assert [s.club_name for s in parse_score_entries(html)] == ["Voorbeeld Golfclub"]
