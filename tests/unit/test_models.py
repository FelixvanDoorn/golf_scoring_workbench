"""Tests for ScrapingResult.get_score_details in pipelines.strokeplay.models."""

import pytest

from pipelines.strokeplay.models import ScrapingResult


def test_empty_score_details_returns_empty_list() -> None:
    assert ScrapingResult(success=True, score_details=[]).get_score_details() == []


def test_none_score_details_becomes_empty_list() -> None:
    result = ScrapingResult(success=False, score_details=None)
    assert result.score_details == []
    assert result.total_scores_found == 0
    assert result.get_score_details() == []


def test_float_scores_are_returned_as_floats() -> None:
    result = ScrapingResult(success=True, score_details=[12, 8.5])
    assert result.get_score_details() == [12.0, 8.5]
    assert result.total_scores_found == 2


def test_dict_scores_parse_comma_decimal_strings() -> None:
    result = ScrapingResult(success=True, score_details=[{"SD": "12,3"}, {"differential": 7}])
    assert result.get_score_details() == [12.3, 7.0]


def test_value_error_falls_through_to_next_key() -> None:
    # "abc" makes float() raise ValueError; the next key must still be tried.
    result = ScrapingResult(
        success=True, score_details=[{"differential": "abc", "score_differential": "9,1"}]
    )
    assert result.get_score_details() == [9.1]


def test_type_error_falls_through_to_next_key() -> None:
    # A list makes float() raise TypeError; the next key must still be tried.
    result = ScrapingResult(success=True, score_details=[{"SD": [1, 2], "score_differential": 4.2}])
    assert result.get_score_details() == [4.2]


@pytest.mark.parametrize("bad_value", ["not-a-number", None, [1], {"x": 1}])
def test_unparseable_values_are_skipped_without_raising(bad_value: object) -> None:
    result = ScrapingResult(success=True, score_details=[{"SD": bad_value}, {"SD": "5,5"}])
    assert result.get_score_details() == [5.5]


def test_dict_without_known_keys_is_skipped() -> None:
    result = ScrapingResult(success=True, score_details=[{"other": 1}, {"SD": 3}])
    assert result.get_score_details() == [3.0]
