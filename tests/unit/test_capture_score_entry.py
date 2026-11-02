"""Tests for pipelines.strokeplay.capture_score_entry.

The driver is a MagicMock, WebDriverWait is patched so nothing waits, and every file
is written under tmp_path. No browser, network, real .env or real DB is touched.
"""

import logging
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

from pipelines.strokeplay import capture_score_entry as cse
from pipelines.strokeplay.capture_score_entry import (
    CAPTURE_DIR,
    ENTRY_SELECTOR,
    CapturedEntry,
    EntryNotFoundError,
    extract_score_entry,
    main,
    render_capture,
    write_capture,
)
from pipelines.strokeplay.models import LoginResult, ScraperConfig
from pipelines.strokeplay.scrapers.golf_nl_scraper import GolfNLScraper

FAKE_EMAIL = "tester@example.invalid"
FAKE_CREDENTIAL = "not-a-real-password"
SENTINEL = "SENTINEL-PERSONAL-DATA"
PRIVATE_PAGE_URL = "https://example.invalid/secret-path"

ENTRY_NO_DETAILS = f'<div class="c-linkBlock c-score"><span>{SENTINEL}</span></div>'
ENTRY_WITH_DETAILS = (
    '<div class="c-linkBlock c-score">'
    f'<div class="c-score__details"><div>{SENTINEL}</div></div>'
    "</div>"
)
# Only a class-name lookalike: must not count as details.
ENTRY_LOOKALIKE = (
    f'<div class="c-linkBlock c-score"><p class="c-score__details-x">{SENTINEL}</p></div>'
)
OUTSIDE_DETAILS = f'<div class="c-score__details"><div>{SENTINEL}-outside</div></div>'
FIXED_NOW = datetime(2000, 1, 1, 0, 0, 0)


def _element(*outer_html: str | Exception) -> MagicMock:
    """A fake WebElement whose successive outerHTML reads return outer_html."""
    element = MagicMock(name="entry")
    element.get_attribute.side_effect = list(outer_html)
    return element


def _driver(entries: list[MagicMock], outside: list[MagicMock] | None = None) -> MagicMock:
    """A fake driver returning entries for the entry selector, outside for details."""
    driver = MagicMock(name="driver")
    driver.current_url = PRIVATE_PAGE_URL

    def find_elements(by: str, value: str) -> list[MagicMock]:
        assert by == By.CSS_SELECTOR
        if value == ENTRY_SELECTOR:
            return entries
        if value == "div.c-score__details":
            return outside or []
        raise AssertionError(f"unexpected selector {value}")

    driver.find_elements.side_effect = find_elements
    return driver


@pytest.fixture(autouse=True)
def fake_wait(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace WebDriverWait so no test waits on a real timeout."""
    wait_cls = MagicMock(name="WebDriverWait")
    monkeypatch.setattr(cse, "WebDriverWait", wait_cls)
    return wait_cls


@pytest.fixture(autouse=True)
def guard_capture_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point CAPTURE_DIR at tmp_path so nothing lands in the real data/captures/."""
    capture_dir = tmp_path / "captures"
    monkeypatch.setattr(cse, "CAPTURE_DIR", capture_dir)
    return capture_dir


# extract_score_entry


def test_inline_details_are_captured_without_click() -> None:
    element = _element(ENTRY_WITH_DETAILS)
    driver = _driver([element])

    entry = extract_score_entry(driver)

    assert entry.mode == "inline"
    assert entry.entry_html == ENTRY_WITH_DETAILS
    assert entry.details_html is None
    element.click.assert_not_called()


def test_expanded_details_use_post_click_html() -> None:
    element = _element(ENTRY_NO_DETAILS, ENTRY_WITH_DETAILS)
    driver = _driver([element])

    entry = extract_score_entry(driver)

    assert entry.mode == "expanded"
    assert entry.entry_html == ENTRY_WITH_DETAILS
    element.click.assert_called_once()
    driver.execute_script.assert_called_once()


def test_lookalike_class_is_not_treated_as_details() -> None:
    element = _element(ENTRY_LOOKALIKE, ENTRY_LOOKALIKE)
    driver = _driver([element])

    entry = extract_score_entry(driver)

    assert entry.mode == "missing"
    element.click.assert_called_once()


def test_outside_details_are_captured_separately(fake_wait: MagicMock) -> None:
    fake_wait.return_value.until.side_effect = TimeoutException("no details")
    element = _element(ENTRY_NO_DETAILS, ENTRY_NO_DETAILS)
    details = MagicMock(name="details")
    details.get_attribute.return_value = OUTSIDE_DETAILS
    driver = _driver([element], outside=[details])

    entry = extract_score_entry(driver, timeout=0.01)

    assert entry.mode == "outside"
    assert entry.entry_html == ENTRY_NO_DETAILS
    assert entry.details_html == OUTSIDE_DETAILS


def test_stale_entry_keeps_pre_click_html_and_falls_through() -> None:
    element = _element(ENTRY_NO_DETAILS, StaleElementReferenceException("gone"))
    details = MagicMock(name="details")
    details.get_attribute.return_value = OUTSIDE_DETAILS
    driver = _driver([element], outside=[details])

    entry = extract_score_entry(driver)

    assert entry.mode == "outside"
    assert entry.entry_html == ENTRY_NO_DETAILS


def test_stale_entry_without_outside_details_is_missing() -> None:
    element = _element(ENTRY_NO_DETAILS, StaleElementReferenceException("gone"))
    driver = _driver([element])

    entry = extract_score_entry(driver)

    assert entry.mode == "missing"
    assert entry.entry_html == ENTRY_NO_DETAILS


def test_missing_details_still_returns_entry(fake_wait: MagicMock) -> None:
    fake_wait.return_value.until.side_effect = TimeoutException("no details")
    element = _element(ENTRY_NO_DETAILS, ENTRY_NO_DETAILS)
    driver = _driver([element])

    entry = extract_score_entry(driver)

    assert entry.mode == "missing"
    assert entry.entry_html == ENTRY_NO_DETAILS
    assert entry.details_html is None


def test_no_entries_raises_entry_not_found() -> None:
    with pytest.raises(EntryNotFoundError) as excinfo:
        extract_score_entry(_driver([]))

    assert "0" in str(excinfo.value)


@pytest.mark.parametrize("index", [1, -1])
def test_index_out_of_range_raises_entry_not_found(index: int) -> None:
    with pytest.raises(EntryNotFoundError):
        extract_score_entry(_driver([_element(ENTRY_WITH_DETAILS)]), index=index)


def test_index_picks_the_matching_entry() -> None:
    first = _element(ENTRY_WITH_DETAILS)
    second_html = ENTRY_WITH_DETAILS.replace(SENTINEL, "second")
    second = _element(second_html)

    entry = extract_score_entry(_driver([first, second]), index=1)

    assert entry.entry_html == second_html
    first.get_attribute.assert_not_called()


# render_capture and write_capture


def test_render_starts_with_unsanitized_header_and_mode() -> None:
    entry = CapturedEntry(entry_html=ENTRY_WITH_DETAILS, details_html=None, mode="inline")

    rendered = render_capture(entry, FIXED_NOW)

    first_line = rendered.splitlines()[0]
    assert first_line.startswith("<!-- RAW golf.nl capture")
    assert "UNSANITIZED" in first_line
    assert "mode=inline" in first_line
    assert "captured_at=2000-01-01T00:00:00" in first_line
    assert ENTRY_WITH_DETAILS in rendered


def test_render_outside_mode_has_entry_then_details() -> None:
    entry = CapturedEntry(entry_html=ENTRY_NO_DETAILS, details_html=OUTSIDE_DETAILS, mode="outside")

    rendered = render_capture(entry, FIXED_NOW)

    entry_pos = rendered.index(ENTRY_NO_DETAILS)
    separator_pos = rendered.index("<!-- details found outside the c-linkBlock entry -->")
    details_pos = rendered.index(OUTSIDE_DETAILS)
    assert entry_pos < separator_pos < details_pos


def test_render_does_not_include_current_url() -> None:
    driver = _driver([_element(ENTRY_WITH_DETAILS)])

    rendered = render_capture(extract_score_entry(driver), FIXED_NOW)

    assert PRIVATE_PAGE_URL not in rendered


def test_write_capture_creates_gitignore_and_utf8_file(tmp_path: Path) -> None:
    content = "<!-- header -->\n<div>Zoë 72</div>\n"

    path = write_capture(content, tmp_path / "out", FIXED_NOW)

    assert path == tmp_path / "out" / "score_entry_20000101-000000.raw.html"
    assert path.read_bytes() == content.encode("utf-8")
    assert (tmp_path / "out" / ".gitignore").read_text(encoding="utf-8") == "*\n"


def test_write_capture_keeps_existing_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*\n# custom\n", encoding="utf-8")

    write_capture("x", tmp_path, FIXED_NOW)

    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == "*\n# custom\n"


def test_write_capture_never_overwrites(tmp_path: Path) -> None:
    path = write_capture("first", tmp_path, FIXED_NOW)

    with pytest.raises(FileExistsError):
        write_capture("second", tmp_path, FIXED_NOW)

    assert path.read_text(encoding="utf-8") == "first"


def test_capture_dir_is_repo_data_captures() -> None:
    assert CAPTURE_DIR.parts[-2:] == ("data", "captures")
    assert (CAPTURE_DIR.parents[1] / "pyproject.toml").is_file()


# main


@pytest.fixture
def fake_config(monkeypatch: pytest.MonkeyPatch) -> ScraperConfig:
    """Make main() load a fake config instead of the real config.yaml and .env."""
    config = ScraperConfig(email=FAKE_EMAIL, password=FAKE_CREDENTIAL, timeout=1)
    monkeypatch.setattr(cse, "load_config", lambda: config)
    return config


@pytest.fixture
def scraper_patches(fake_config: ScraperConfig) -> Iterator[dict[str, MagicMock]]:
    """Patch GolfNLScraper's driver setup, login and wait; yield the mocks."""
    driver = _driver([_element(ENTRY_WITH_DETAILS)])
    with (
        patch.object(GolfNLScraper, "_setup_driver", return_value=driver) as setup,
        patch.object(GolfNLScraper, "login", return_value=LoginResult(success=True)) as login,
        patch.object(GolfNLScraper, "_wait_for_element") as wait,
    ):
        yield {"driver": driver, "setup": setup, "login": login, "wait": wait}


def _assert_private(caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]) -> None:
    """Assert no HTML, credential or URL reached logs or stdout/stderr."""
    captured = capsys.readouterr()
    for text in (caplog.text, captured.out, captured.err):
        for secret in (SENTINEL, FAKE_EMAIL, FAKE_CREDENTIAL, PRIVATE_PAGE_URL):
            assert secret not in text


def _raw_files(directory: Path) -> list[Path]:
    """List .raw.html files in directory (empty if it does not exist)."""
    return sorted(directory.glob("*.raw.html")) if directory.exists() else []


def test_main_success_writes_one_capture(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)

    assert main([]) == 0

    files = _raw_files(guard_capture_dir)
    assert len(files) == 1
    assert "mode=inline" in files[0].read_text(encoding="utf-8")
    scraper_patches["driver"].quit.assert_called_once()
    scraper_patches["driver"].get.assert_called_once_with("https://mijn.golf.nl/mijn-spel/scores")
    assert str(files[0]) in caplog.text
    _assert_private(caplog, capsys)


def test_main_missing_details_returns_2_and_writes(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    fake_wait: MagicMock,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    fake_wait.return_value.until.side_effect = TimeoutException("no details")
    driver = _driver([_element(ENTRY_NO_DETAILS, ENTRY_NO_DETAILS)])
    scraper_patches["setup"].return_value = driver

    assert main(["--index", "0"]) == 2

    assert len(_raw_files(guard_capture_dir)) == 1
    driver.quit.assert_called_once()
    _assert_private(caplog, capsys)


def test_main_failed_login_returns_1_without_capture(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    scraper_patches["login"].return_value = LoginResult(
        success=False, error_message=f"bad login for {FAKE_EMAIL}"
    )

    assert main([]) == 1

    assert _raw_files(guard_capture_dir) == []
    scraper_patches["driver"].get.assert_not_called()
    scraper_patches["driver"].quit.assert_called_once()
    _assert_private(caplog, capsys)


def test_main_webdriver_error_returns_1_and_quits(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    scraper_patches["driver"].get.side_effect = WebDriverException(f"failed at {PRIVATE_PAGE_URL}")

    assert main([]) == 1

    assert _raw_files(guard_capture_dir) == []
    scraper_patches["driver"].quit.assert_called_once()
    _assert_private(caplog, capsys)


def test_main_index_out_of_range_returns_1(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)

    assert main(["--index", "5"]) == 1

    assert _raw_files(guard_capture_dir) == []
    scraper_patches["driver"].quit.assert_called_once()
    _assert_private(caplog, capsys)


def test_main_unexpected_error_propagates_and_quits(
    scraper_patches: dict[str, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> CapturedEntry:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(cse, "extract_score_entry", boom)

    with pytest.raises(RuntimeError):
        main([])

    scraper_patches["driver"].quit.assert_called_once()


def test_main_config_error_returns_1_without_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args: object, **kwargs: object) -> ScraperConfig:
        raise FileNotFoundError("config.yaml")

    monkeypatch.setattr(cse, "load_config", missing)

    with patch.object(GolfNLScraper, "_setup_driver") as setup:
        assert main([]) == 1

    setup.assert_not_called()


def test_main_help_exits_0_without_config_or_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    load = MagicMock(name="load_config")
    monkeypatch.setattr(cse, "load_config", load)

    with (
        patch.object(GolfNLScraper, "_setup_driver") as setup,
        pytest.raises(SystemExit) as excinfo,
    ):
        main(["--help"])

    assert excinfo.value.code == 0
    load.assert_not_called()
    setup.assert_not_called()


# Tester additions (gsw-7e0): privacy and no-overwrite guarantees end to end.


class _FixedDatetime(datetime):
    """datetime whose now() is FIXED_NOW, so main() picks a predictable file name."""

    @classmethod
    def now(cls, tz: object = None) -> _FixedDatetime:
        return cls(2000, 1, 1, 0, 0, 0)


def test_main_never_overwrites_existing_capture(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(cse, "datetime", _FixedDatetime)
    guard_capture_dir.mkdir(parents=True)
    existing = guard_capture_dir / "score_entry_20000101-000000.raw.html"
    existing.write_text("hand-obfuscated", encoding="utf-8")

    assert main([]) == 1

    assert existing.read_text(encoding="utf-8") == "hand-obfuscated"
    assert _raw_files(guard_capture_dir) == [existing]
    scraper_patches["driver"].quit.assert_called_once()
    _assert_private(caplog, capsys)


def test_main_driver_setup_failure_returns_1_without_quit_error(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    scraper_patches["setup"].side_effect = WebDriverException(f"no chrome {PRIVATE_PAGE_URL}")

    assert main([]) == 1

    assert not guard_capture_dir.exists()
    scraper_patches["login"].assert_not_called()
    scraper_patches["driver"].quit.assert_not_called()
    _assert_private(caplog, capsys)


def test_main_entry_wait_timeout_returns_1_and_quits(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    scraper_patches["wait"].side_effect = TimeoutException("no entries")

    assert main([]) == 1

    assert _raw_files(guard_capture_dir) == []
    scraper_patches["driver"].quit.assert_called_once()
    _assert_private(caplog, capsys)


def test_main_outside_mode_writes_entry_then_details_privately(
    scraper_patches: dict[str, MagicMock],
    guard_capture_dir: Path,
    fake_wait: MagicMock,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    fake_wait.return_value.until.side_effect = TimeoutException("no details")
    details = MagicMock(name="details")
    details.get_attribute.return_value = OUTSIDE_DETAILS
    driver = _driver([_element(ENTRY_NO_DETAILS, ENTRY_NO_DETAILS)], outside=[details])
    scraper_patches["setup"].return_value = driver

    assert main([]) == 0

    files = _raw_files(guard_capture_dir)
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "mode=outside" in text
    assert PRIVATE_PAGE_URL not in text
    assert FAKE_EMAIL not in text
    assert FAKE_CREDENTIAL not in text
    assert text.index(ENTRY_NO_DETAILS) < text.index(OUTSIDE_DETAILS)
    driver.quit.assert_called_once()
    _assert_private(caplog, capsys)
