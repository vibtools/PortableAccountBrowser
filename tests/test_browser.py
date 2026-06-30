from pathlib import Path

import pytest

from epb.browser import discover_chromium


def test_discover_chromium_in_nested_runtime(tmp_path: Path) -> None:
    executable = tmp_path / "build" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test")
    assert discover_chromium(tmp_path) == executable.resolve()


def test_discover_chromium_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_chromium(tmp_path)
