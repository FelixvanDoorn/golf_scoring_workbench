"""Importing the import-safe strokeplay modules must not start a browser or read .env."""

import subprocess
import sys
import textwrap
from pathlib import Path

# Runs in a fresh interpreter so the modules are imported for the first time there,
# regardless of what other tests already imported in this process.
_PROBE = textwrap.dedent(
    """
    import os
    import sys
    import dotenv
    import selenium.webdriver
    import webdriver_manager.chrome

    calls = []

    def _trap(name):
        def _fn(*args, **kwargs):
            calls.append(name)
            raise RuntimeError(name + " called at import time")
        return _fn

    selenium.webdriver.Chrome = _trap("webdriver.Chrome")
    webdriver_manager.chrome.ChromeDriverManager.install = _trap("ChromeDriverManager.install")
    dotenv.dotenv_values = _trap("dotenv_values")
    dotenv.load_dotenv = _trap("load_dotenv")

    _real_open = open
    def _guarded_open(file, *args, **kwargs):
        if os.path.basename(str(file)) == ".env":
            calls.append("open(.env)")
            raise RuntimeError(".env opened at import time")
        return _real_open(file, *args, **kwargs)
    import builtins
    builtins.open = _guarded_open

    for name in sys.argv[1:]:
        __import__(name)

    print("CALLS=" + ",".join(calls))
    """
)

IMPORT_SAFE = [
    "pipelines.strokeplay.models",
    "pipelines.strokeplay.config_manager",
    "pipelines.strokeplay.scrapers",
    "pipelines.strokeplay.scrapers.base_scraper",
    "pipelines.strokeplay.scrapers.golf_nl_scraper",
    "pipelines.strokeplay.scrapers.example_scraper",
    "pipelines.strokeplay.scrape_strokeplay_data",
    "pipelines.strokeplay.models_example",
]


def test_import_safe_modules_have_no_browser_or_env_side_effects(tmp_path: Path) -> None:
    # cwd=tmp_path also proves the package resolves via the install, not via the repo cwd.
    result = subprocess.run(  # noqa: S603 - fixed argv: our interpreter + constant probe
        [sys.executable, "-c", _PROBE, *IMPORT_SAFE],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CALLS="


def test_no_module_in_package_uses_sys_path_hacks() -> None:
    import pipelines

    package_root = Path(pipelines.__file__).parent
    offenders = [
        str(path.relative_to(package_root))
        for path in package_root.rglob("*.py")
        if "sys.path" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
