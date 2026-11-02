"""Offline tests for pipelines.strokeplay.scrapers.golf_nl_parser.

All input comes from synthetic HTML fixtures under tests/fixtures/golf_nl.
"""

import logging
from collections.abc import Callable

import pytest

from pipelines.strokeplay.scrapers import golf_nl_parser
from pipelines.strokeplay.scrapers.golf_nl_parser import (
    parse_score_details_block,
    parse_scores_page,
)

LoadHtml = Callable[[str], str]

EXPECTED_BLOCK = {"Tee": "Rood", "Qualifying": "Ja", "Stableford": "36"}

EXPECTED_PAGE = [
    {
        "Datum": "2000-01-01",
        "Tee": "Geel",
        "Qualifying": "Ja",
        "Stableford": "36",
        "Score differential": "12,3",
    },
    {
        "Datum": "2000-01-02",
        "Tee": "Rood",
        "Qualifying": "Nee",
        "Marker": "Marker A",
    },
    {
        "Datum": "2000-01-03",
        "Tee": "Wit",
        "Stableford": "30",
        "Marker": "Marker B",
        "Getekend": "Ja",
        "Scorekaart": "Bekijk",
    },
]

ROW_TEMPLATE = (
    '<div class="c-score__details__content">'
    '<div class="c-score__details__label">{label}</div>'
    '<div class="c-score__details__text">{text}</div>'
    "</div>"
)


def _block(*rows: tuple[str, str]) -> str:
    inner = "".join(ROW_TEMPLATE.format(label=label, text=text) for label, text in rows)
    return f'<div class="c-score__details">{inner}</div>'


def test_block_fixture_yields_expected_dict(golf_nl_html: LoadHtml) -> None:
    result = parse_score_details_block(golf_nl_html("score_details_block.html"))

    assert result == EXPECTED_BLOCK


def test_block_fixture_skips_empty_label_and_missing_text(golf_nl_html: LoadHtml) -> None:
    result = parse_score_details_block(golf_nl_html("score_details_block.html"))

    assert "" not in result
    assert "orphan value" not in result.values()
    assert "Marker" not in result


def test_block_fixture_duplicate_label_keeps_last_value(golf_nl_html: LoadHtml) -> None:
    result = parse_score_details_block(golf_nl_html("score_details_block.html"))

    assert result["Tee"] == "Rood"


def test_block_parser_accepts_details_div_as_root() -> None:
    html = _block(("Tee", "Geel"), ("Stableford", "36"))

    assert parse_score_details_block(html) == {"Tee": "Geel", "Stableford": "36"}


def test_block_parser_accepts_nested_details_div() -> None:
    html = f'<html><body><section class="wrap"><div>{_block(("Tee", "Geel"))}</div></section>'
    html += "</body></html>"

    assert parse_score_details_block(html) == {"Tee": "Geel"}


def test_block_parser_without_details_div_reads_rows_from_whole_document() -> None:
    html = ROW_TEMPLATE.format(label="Tee", text="Geel")

    assert parse_score_details_block(html) == {"Tee": "Geel"}


def test_block_parser_only_reads_first_details_div() -> None:
    html = _block(("Tee", "Geel")) + _block(("Tee", "Rood"))

    assert parse_score_details_block(html) == {"Tee": "Geel"}


def test_values_are_stripped_and_nested_markup_flattened() -> None:
    html = _block(
        ("  Score differential\n ", "\n   <span>12,3</span>\n  "), ("Tee", " <b>Ge</b>el ")
    )

    assert parse_score_details_block(html) == {"Score differential": "12,3", "Tee": "Geel"}


def test_page_fixture_nested_span_value_is_flattened(golf_nl_html: LoadHtml) -> None:
    scores = parse_scores_page(golf_nl_html("scores_page.html"))

    assert scores[0]["Score differential"] == "12,3"


def test_scores_page_yields_three_dicts_in_document_order(golf_nl_html: LoadHtml) -> None:
    scores = parse_scores_page(golf_nl_html("scores_page.html"))

    assert scores == EXPECTED_PAGE
    assert [list(score) for score in scores] == [list(score) for score in EXPECTED_PAGE]


def test_empty_scores_page_yields_empty_list(golf_nl_html: LoadHtml) -> None:
    assert parse_scores_page(golf_nl_html("scores_page_empty.html")) == []


def test_empty_details_block_is_dropped_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    html = (
        '<div class="c-scores">'
        + _block(("Tee", "Geel"))
        + '<div class="c-score__details"></div>'
        + _block(("Tee", "Rood"))
        + "</div>"
    )

    with caplog.at_level(logging.WARNING, logger=golf_nl_parser.__name__):
        scores = parse_scores_page(html)

    assert scores == [{"Tee": "Geel"}, {"Tee": "Rood"}]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].name == golf_nl_parser.__name__
    assert "Score 2" in warnings[0].getMessage()


@pytest.mark.parametrize("html", ["", "   ", "<p>no scores here</p>"])
def test_parsers_return_empty_for_html_without_rows(html: str) -> None:
    assert parse_score_details_block(html) == {}
    assert parse_scores_page(html) == []


def test_malformed_html_is_parsed_without_raising() -> None:
    html = (
        '<div class="c-scores"><div class="c-score__details">'
        '<div class="c-score__details__content">'
        '<div class="c-score__details__label">Tee'
        '<div class="c-score__details__text">Geel'
    )

    # html.parser nests the unclosed text div inside the label div, so the label
    # text swallows the value. This pins the current (pre-existing) behaviour.
    assert parse_scores_page(html) == [{"TeeGeel": "Geel"}]


def test_non_div_elements_with_selector_classes_are_ignored() -> None:
    html = (
        '<span class="c-score__details">'
        '<div class="c-score__details__content">'
        '<span class="c-score__details__label">Tee</span>'
        '<div class="c-score__details__text">Geel</div>'
        "</div></span>"
    )

    assert parse_scores_page(html) == []
    assert parse_score_details_block(html) == {}
