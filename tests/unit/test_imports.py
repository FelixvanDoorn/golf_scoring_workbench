"""Check that pipelines.strokeplay imports as a package, without sys.path hacks."""

import ast
import importlib
from pathlib import Path

import pytest

import pipelines.strokeplay

STROKEPLAY_DIR = Path(pipelines.strokeplay.__file__).parent

# Flat module names that only resolved through the old sys.path hacks.
LEGACY_FLAT_MODULES = {"models", "config_manager", "scrapers", "golf_nl_scraper"}

IMPORT_SAFE_MODULES: dict[str, tuple[str, ...]] = {
    "pipelines.strokeplay.models": ("ScraperConfig", "ScrapingResult", "LoginResult", "GolfScore"),
    "pipelines.strokeplay.config_manager": ("load_config", "ConfigManager"),
    "pipelines.strokeplay.scrapers": ("BaseScraper", "GolfNLScraper"),
    "pipelines.strokeplay.scrapers.base_scraper": ("BaseScraper",),
    "pipelines.strokeplay.scrapers.golf_nl_scraper": ("GolfNLScraper",),
    "pipelines.strokeplay.scrapers.example_scraper": ("ExampleScraper",),
    "pipelines.strokeplay.scrape_strokeplay_data": ("main", "ScraperOrchestrator"),
    "pipelines.strokeplay.models_example": ("main",),
}

# These scripts run Selenium and load config at import time, so they are only parsed.
SIDE_EFFECT_SCRIPTS = ("strokeplay_pipeline.py", "debug_html.py")


@pytest.mark.parametrize(("module_name", "names"), IMPORT_SAFE_MODULES.items())
def test_module_imports_and_exposes_public_names(module_name: str, names: tuple[str, ...]) -> None:
    module = importlib.import_module(module_name)

    missing = [name for name in names if not hasattr(module, name)]
    assert missing == []


def test_scrapers_share_one_base_class() -> None:
    from pipelines.strokeplay.scrapers import BaseScraper, GolfNLScraper

    assert issubclass(GolfNLScraper, BaseScraper)


@pytest.mark.parametrize("script", SIDE_EFFECT_SCRIPTS)
def test_side_effect_scripts_use_package_imports(script: str) -> None:
    tree = ast.parse((STROKEPLAY_DIR / script).read_text(encoding="utf-8"))

    flat_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module is not None
        and node.module.split(".")[0] in LEGACY_FLAT_MODULES
    ]
    flat_imports += [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.split(".")[0] in LEGACY_FLAT_MODULES
    ]
    assert flat_imports == []


@pytest.mark.parametrize("script", SIDE_EFFECT_SCRIPTS)
def test_side_effect_scripts_import_from_package(script: str) -> None:
    tree = ast.parse((STROKEPLAY_DIR / script).read_text(encoding="utf-8"))

    package_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("pipelines.strokeplay.")
    ]
    assert package_imports != []
