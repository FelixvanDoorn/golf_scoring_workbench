"""Shared pytest fixtures for the test suite."""

from collections.abc import Callable
from pathlib import Path

import pytest

GOLF_NL_FIXTURES = Path(__file__).parent / "fixtures" / "golf_nl"


@pytest.fixture
def golf_nl_html() -> Callable[[str], str]:
    """Return a loader that reads a synthetic golf.nl HTML fixture by file name."""

    def load(name: str) -> str:
        return (GOLF_NL_FIXTURES / name).read_text(encoding="utf-8")

    return load
