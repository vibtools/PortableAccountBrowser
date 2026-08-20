from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "package_publish_release.py"
SPEC = importlib.util.spec_from_file_location("package_publish_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_public_layout(root: Path) -> None:
    for relative in (
        "_internal",
        "runtime/chromium",
        "data/profiles",
        "data/downloads",
        "data/logs",
        "data/temp",
        "data/crash",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    for relative in (
        "PortableAccountBrowser.exe",
        "runtime/chromium/chrome.exe",
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "PRIVACY.md",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    for relative in ("profiles", "downloads", "logs", "temp", "crash"):
        (root / "data" / relative / ".keep").write_text("clean", encoding="ascii")
    (root / "PORTABLE_BUILD_MODE.txt").write_text("PUBLIC CLEAN BUILD", encoding="utf-8")
    (root / "VERSION").write_text("1.3.1", encoding="utf-8")


def test_clean_public_layout_is_accepted(tmp_path: Path) -> None:
    make_public_layout(tmp_path)
    MODULE.validate_public_binary(tmp_path, "1.3.1")


def test_profiles_database_is_rejected(tmp_path: Path) -> None:
    make_public_layout(tmp_path)
    (tmp_path / "data" / "profiles.sqlite3").write_bytes(b"private")
    with pytest.raises(RuntimeError):
        MODULE.validate_public_binary(tmp_path, "1.3.1")


def test_cookie_file_is_rejected(tmp_path: Path) -> None:
    make_public_layout(tmp_path)
    cookie = tmp_path / "data" / "profiles" / "abc" / "Default" / "Network" / "Cookies"
    cookie.parent.mkdir(parents=True)
    cookie.write_bytes(b"private")
    with pytest.raises(RuntimeError):
        MODULE.validate_public_binary(tmp_path, "1.3.1")


def test_publish_builder_has_external_release_default() -> None:
    text = (ROOT / "scripts" / "build_publish_release.ps1").read_text(encoding="utf-8")
    assert r'D:\Project\Python\Mailbox\release' in text
    assert "Grant-ReleaseRootAccess" in text
    assert "RequireCleanPublic" in text
    assert "CertificateThumbprint" in text
    assert "sign_release.ps1" in text


def test_unsigned_release_is_documented() -> None:
    build = (ROOT / "BUILD.md").read_text(encoding="utf-8")
    publishing = (ROOT / "PUBLISHING.md").read_text(encoding="utf-8")

    assert "Build without an Authenticode certificate" in build
    assert "without `-CertificateThumbprint`" in publishing
    assert "SmartScreen" in build
    assert "SmartScreen" in publishing


def test_ci_runs_ruff() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python -m ruff check ." in workflow


def test_repository_publish_files_exist() -> None:
    for name in (
        "README.md",
        "PRIVACY.md",
        "PUBLISHING.md",
        "CODE_OF_CONDUCT.md",
        ".github/workflows/ci.yml",
        "build_publish_ready.bat",
        "verify_publish_release.bat",
    ):
        assert (ROOT / name).is_file(), name


def test_complete_source_stage_is_created(tmp_path: Path) -> None:
    source_root = MODULE.build_source_stage(ROOT, tmp_path / "stage", "1.3.1")
    assert (source_root / "app.py").is_file()
    assert (source_root / "epb" / "browser.py").is_file()
    assert (source_root / ".github" / "workflows" / "ci.yml").is_file()
    assert (source_root / "SOURCE_MANIFEST.sha256").stat().st_size > 1000
    assert not (source_root / ".venv").exists()


def test_source_stage_rejects_sensitive_browser_file(tmp_path: Path) -> None:
    source_root = MODULE.build_source_stage(ROOT, tmp_path / "stage", "1.3.1")
    cookie = source_root / "tests" / "fixture" / "Default" / "Network" / "Cookies"
    cookie.parent.mkdir(parents=True)
    cookie.write_bytes(b"private")

    with pytest.raises(RuntimeError, match="Sensitive browser/account file"):
        MODULE.validate_source_stage(source_root, "1.3.1")


def test_source_copy_rejects_symbolic_link(tmp_path: Path) -> None:
    target = tmp_path / "private.txt"
    target.write_text("private", encoding="utf-8")
    link = tmp_path / "README.md"
    link.symlink_to(target)

    with pytest.raises(RuntimeError, match="Symbolic links"):
        MODULE.copy_file(link, tmp_path / "stage" / "README.md")


def test_source_directory_copy_rejects_root_symbolic_link(tmp_path: Path) -> None:
    private = tmp_path / "private"
    private.mkdir()
    (private / "secret.txt").write_text("private", encoding="utf-8")
    link = tmp_path / "assets"
    link.symlink_to(private, target_is_directory=True)

    with pytest.raises(RuntimeError, match="Symbolic links"):
        MODULE.copy_source_directory(link, tmp_path / "stage" / "assets")

    assert not (tmp_path / "stage" / "assets" / "secret.txt").exists()
