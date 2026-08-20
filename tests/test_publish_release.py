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


def write_manifest(root: Path, relative_paths: tuple[str, ...]) -> None:
    lines = []
    for relative in sorted(relative_paths, key=str.casefold):
        lines.append(f"{MODULE.sha256_file(root / relative)}  {relative}")
    (root / MODULE.SOURCE_MANIFEST_NAME).write_text("\n".join(lines) + "\n", encoding="ascii")


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
    entries = MODULE.read_source_manifest(source_root)
    expected = {relative.as_posix() for _, relative in entries}
    actual = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file() and path.name != MODULE.SOURCE_MANIFEST_NAME
    }
    assert actual == expected


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


@pytest.mark.parametrize(
    "line, message",
    (
        ("not-a-hash  app.py\n", "Malformed"),
        (f"{'0' * 64}  ../private.txt\n", "Unsafe"),
        (f"{'0' * 64}  /private.txt\n", "Unsafe"),
        (f"{'0' * 64}  C:/private.txt\n", "Unsafe"),
        (f"{'0' * 64}  tests/private.txt:stream\n", "Unsafe"),
        (f"{'0' * 64}  tests/NUL.txt\n", "Unsafe"),
        (f"{'0' * 64}  tests\\private.txt\n", "Unsafe"),
        (f"{'0' * 64}  tests/./private.txt\n", "Unsafe"),
        (f"{'0' * 64}  SOURCE_MANIFEST.sha256\n", "Unsafe"),
    ),
)
def test_source_manifest_rejects_malformed_or_unsafe_entry(
    tmp_path: Path, line: str, message: str
) -> None:
    (tmp_path / MODULE.SOURCE_MANIFEST_NAME).write_text(line, encoding="ascii")

    with pytest.raises(RuntimeError, match=message):
        MODULE.read_source_manifest(tmp_path)


def test_source_manifest_rejects_checksum_mismatch(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("safe", encoding="utf-8")
    (tmp_path / MODULE.SOURCE_MANIFEST_NAME).write_text(
        f"{'0' * 64}  app.py\n", encoding="ascii"
    )

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        MODULE.read_source_manifest(tmp_path)


def test_source_manifest_rejects_missing_input(tmp_path: Path) -> None:
    (tmp_path / MODULE.SOURCE_MANIFEST_NAME).write_text(
        f"{'0' * 64}  missing.py\n", encoding="ascii"
    )

    with pytest.raises(RuntimeError, match="Missing, non-file"):
        MODULE.read_source_manifest(tmp_path)


def test_source_manifest_requires_deterministic_order(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "z.py").write_text("z", encoding="utf-8")
    a_digest = MODULE.sha256_file(tmp_path / "a.py")
    z_digest = MODULE.sha256_file(tmp_path / "z.py")
    (tmp_path / MODULE.SOURCE_MANIFEST_NAME).write_text(
        f"{z_digest}  z.py\n{a_digest}  a.py\n", encoding="ascii"
    )

    with pytest.raises(RuntimeError, match="deterministic"):
        MODULE.read_source_manifest(tmp_path)


def test_source_manifest_rejects_duplicate_casefolded_path(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("one", encoding="utf-8")
    (tmp_path / "readme.md").write_text("two", encoding="utf-8")
    first = MODULE.sha256_file(tmp_path / "README.md")
    second = MODULE.sha256_file(tmp_path / "readme.md")
    (tmp_path / MODULE.SOURCE_MANIFEST_NAME).write_text(
        f"{first}  README.md\n{second}  readme.md\n", encoding="ascii"
    )

    with pytest.raises(RuntimeError, match="case-colliding"):
        MODULE.read_source_manifest(tmp_path)


def test_source_manifest_rejects_symbolic_input(tmp_path: Path) -> None:
    target = tmp_path / "target.py"
    target.write_text("safe", encoding="utf-8")
    (tmp_path / "app.py").symlink_to(target)
    write_manifest(tmp_path, ("app.py",))

    with pytest.raises(RuntimeError, match="symbolic source input"):
        MODULE.read_source_manifest(tmp_path)


def test_unlisted_source_tree_file_is_rejected(tmp_path: Path) -> None:
    private = tmp_path / "tests" / "customer-export.bin"
    private.parent.mkdir(parents=True)
    private.write_bytes(b"private")

    with pytest.raises(RuntimeError, match="Unlisted file"):
        MODULE.reject_unlisted_source_files(tmp_path, set())


def test_modified_staged_source_is_rejected(tmp_path: Path) -> None:
    source_root = MODULE.build_source_stage(ROOT, tmp_path / "stage", "1.3.1")
    (source_root / "app.py").write_text("modified", encoding="utf-8")

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        MODULE.validate_source_stage(source_root, "1.3.1")
