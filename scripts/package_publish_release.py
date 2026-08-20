from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable, NoReturn

SOURCE_MANIFEST_NAME = "SOURCE_MANIFEST.sha256"
SOURCE_SCAN_ROOTS = (".github", "assets", "docs", "epb", "scripts", "tests")
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
SENSITIVE_FILE_NAMES = {
    "cookies",
    "cookies-journal",
    "login data",
    "login data-journal",
    "history",
    "history-journal",
    "web data",
    "web data-journal",
    "preferences",
    "secure preferences",
    "transportsecurity",
    "network persistent state",
    "profiles.sqlite3",
    "profiles.sqlite3-wal",
    "profiles.sqlite3-shm",
    "ui_settings.json",
}
ALLOWED_PUBLIC_DATA_FILES = {".keep", ".gitkeep"}


def fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def copy_file(source: Path, destination: Path) -> None:
    if source.is_symlink():
        fail(f"Symbolic links are not permitted in the source release: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def should_skip_source(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    return (
        "__pycache__" in parts
        or ".pytest_cache" in parts
        or name.endswith((".pyc", ".pyo", ".bak", ".tmp"))
        or name.startswith("fix_")
    )


def read_source_manifest(root: Path) -> list[tuple[str, Path]]:
    """Read and verify the canonical source-release inventory."""
    root = Path(root).resolve()
    manifest_path = root / SOURCE_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        fail(f"Missing or symbolic source manifest: {manifest_path}")

    entries: list[tuple[str, Path]] = []
    seen_paths: set[str] = set()
    previous_sort_key: str | None = None
    try:
        lines = manifest_path.read_text(encoding="ascii").splitlines()
    except UnicodeError:
        fail("Source manifest must contain ASCII text only.")

    for line_number, line in enumerate(lines, start=1):
        digest, separator, relative_text = line.partition("  ")
        if separator != "  " or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            fail(f"Malformed source manifest entry at line {line_number}.")
        if not relative_text or "\\" in relative_text or any(
            ord(character) < 32 or ord(character) == 127 for character in relative_text
        ):
            fail(f"Unsafe source manifest path at line {line_number}: {relative_text!r}")

        pure_path = PurePosixPath(relative_text)
        unsafe_windows_part = any(
            ":" in part
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
            for part in pure_path.parts
        )
        if (
            pure_path.is_absolute()
            or pure_path.as_posix() != relative_text
            or any(part in {"", ".", ".."} for part in pure_path.parts)
            or unsafe_windows_part
            or pure_path.as_posix() == SOURCE_MANIFEST_NAME
        ):
            fail(f"Unsafe source manifest path at line {line_number}: {relative_text!r}")

        normalized = pure_path.as_posix()
        sort_key = normalized.casefold()
        if sort_key in seen_paths:
            fail(f"Duplicate or case-colliding source manifest path: {normalized}")
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            fail("Source manifest entries must use deterministic case-insensitive ordering.")
        seen_paths.add(sort_key)
        previous_sort_key = sort_key

        source = root.joinpath(*pure_path.parts)
        if source.is_symlink() or not source.is_file():
            fail(f"Missing, non-file, or symbolic source input: {normalized}")
        resolved = source.resolve()
        if root not in resolved.parents:
            fail(f"Source manifest path escaped the project root: {normalized}")
        if sha256_file(source) != digest:
            fail(f"Source manifest checksum mismatch: {normalized}")
        entries.append((digest, Path(*pure_path.parts)))

    if not entries:
        fail("Source manifest is empty.")
    return entries


def reject_unlisted_source_files(project_root: Path, listed: set[str]) -> None:
    """Reject unexpected files in recursively maintained source directories."""
    for root_name in SOURCE_SCAN_ROOTS:
        scan_root = project_root / root_name
        if not scan_root.is_dir():
            continue
        for path in scan_root.rglob("*"):
            relative_path = path.relative_to(project_root)
            if should_skip_source(relative_path):
                continue
            relative = relative_path.as_posix()
            if path.is_symlink():
                fail(f"Symbolic link in source release tree: {relative}")
            if path.is_dir():
                continue
            if relative.casefold() not in listed:
                fail(f"Unlisted file in source release tree: {relative}")


def build_source_stage(project_root: Path, stage_root: Path, version: str) -> Path:
    project_root = Path(project_root).resolve()
    entries = read_source_manifest(project_root)
    listed = {relative.as_posix().casefold() for _, relative in entries}
    reject_unlisted_source_files(project_root, listed)

    remove_tree(stage_root)
    source_root = stage_root / f"PortableAccountBrowser_Source_v{version}"
    source_root.mkdir(parents=True)

    for expected_digest, relative in entries:
        source = project_root / relative
        destination = source_root / relative
        copy_file(source, destination)
        if sha256_file(destination) != expected_digest:
            fail(f"Staged source checksum mismatch: {relative.as_posix()}")
    copy_file(project_root / SOURCE_MANIFEST_NAME, source_root / SOURCE_MANIFEST_NAME)

    validate_source_stage(source_root, version)
    return source_root


def validate_source_stage(source_root: Path, version: str) -> None:
    entries = read_source_manifest(source_root)
    expected_files = {relative.as_posix().casefold() for _, relative in entries}
    expected_files.add(SOURCE_MANIFEST_NAME.casefold())
    required = (
        "app.py",
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "PRIVACY.md",
        "PUBLISHING.md",
        "epb/browser.py",
        "epb/ui.py",
        "scripts/build_publish_release.ps1",
        "scripts/package_publish_release.py",
        "tests/test_publish_release.py",
        ".github/workflows/ci.yml",
        "SOURCE_MANIFEST.sha256",
        "VERSION",
    )
    missing = [name for name in required if not (source_root / name).is_file()]
    if missing:
        fail("Incomplete source package. Missing: " + ", ".join(missing))
    if (source_root / "VERSION").read_text(encoding="utf-8").strip() != version:
        fail("Source package VERSION mismatch.")
    forbidden_roots = (".venv", "build", "dist", "release", "pab", "pab_public")
    for name in forbidden_roots:
        if (source_root / name).exists():
            fail(f"Development/private directory leaked into source package: {name}")
    files = [path for path in source_root.rglob("*") if path.is_file()]
    if len(files) < 65:
        fail(f"Source package is unexpectedly small ({len(files)} files).")
    for path in files:
        relative = path.relative_to(source_root)
        if should_skip_source(relative):
            fail(f"Temporary file leaked into source package: {path}")
        if path.name.casefold() in SENSITIVE_FILE_NAMES:
            fail(f"Sensitive browser/account file leaked into source package: {path}")
        if relative.as_posix().casefold() not in expected_files:
            fail(f"Unlisted file leaked into source package: {relative.as_posix()}")

    data_root = source_root / "data"
    for path in data_root.rglob("*"):
        if path.is_file() and path.name.casefold() not in ALLOWED_PUBLIC_DATA_FILES:
            fail(f"Source package contains application/user data: {path.relative_to(source_root)}")


def validate_public_binary(binary_root: Path, version: str) -> None:
    required = (
        "PortableAccountBrowser.exe",
        "_internal",
        "runtime/chromium/chrome.exe",
        "data/profiles",
        "data/downloads",
        "data/logs",
        "data/temp",
        "data/crash",
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "PRIVACY.md",
        "PORTABLE_BUILD_MODE.txt",
        "VERSION",
    )
    missing = [name for name in required if not (binary_root / name).exists()]
    if missing:
        fail("Incomplete public binary layout. Missing: " + ", ".join(missing))

    mode_text = (binary_root / "PORTABLE_BUILD_MODE.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    if "PUBLIC CLEAN BUILD" not in mode_text:
        fail("Binary package is not marked as a clean public build.")
    if (binary_root / "VERSION").read_text(encoding="utf-8").strip() != version:
        fail("Binary package VERSION mismatch.")

    forbidden_top = (".venv", "tests", "app.py", "EmailPortableBrowser.spec", "build")
    for name in forbidden_top:
        if (binary_root / name).exists():
            fail(f"Development item leaked into binary package: {name}")

    data_root = binary_root / "data"
    for path in data_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.casefold() not in ALLOWED_PUBLIC_DATA_FILES:
            fail(f"Public binary contains application/user data: {path.relative_to(binary_root)}")

    for path in binary_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.casefold() in SENSITIVE_FILE_NAMES:
            fail(f"Sensitive browser/account file leaked: {path.relative_to(binary_root)}")
        lower_parts = [part.casefold() for part in path.relative_to(binary_root).parts]
        if "update_backups" in lower_parts:
            fail(f"Update backup leaked into public binary: {path.relative_to(binary_root)}")


def zip_tree(root: Path, output: Path, archive_root_name: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    output.unlink(missing_ok=True)

    fixed_time = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        root_info = zipfile.ZipInfo(archive_root_name.rstrip("/") + "/", fixed_time)
        root_info.external_attr = (stat.S_IFDIR | 0o755) << 16
        archive.writestr(root_info, b"")

        for path in sorted(root.rglob("*"), key=lambda value: value.as_posix().casefold()):
            relative = path.relative_to(root).as_posix()
            arcname = f"{archive_root_name}/{relative}"
            if path.is_symlink():
                fail(f"Symbolic link cannot be archived: {path}")
            if path.is_dir():
                info = zipfile.ZipInfo(arcname.rstrip("/") + "/", fixed_time)
                info.external_attr = (stat.S_IFDIR | 0o755) << 16
                archive.writestr(info, b"")
            elif path.is_file():
                # Stream files into the archive. Chromium includes large binaries,
                # so reading each file fully into memory would be unnecessary.
                archive.write(path, arcname)

    os.replace(temporary, output)


def validate_zip(path: Path, required_suffixes: Iterable[str], minimum_files: int) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        fail(f"ZIP was not created: {path}")
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        if bad:
            fail(f"ZIP CRC validation failed at: {bad}")
        names = archive.namelist()
        files = [name for name in names if not name.endswith("/")]
        if len(files) < minimum_files:
            fail(f"ZIP is unexpectedly small ({len(files)} files): {path.name}")
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                fail(f"ZIP is missing required entry '{suffix}': {path.name}")


def write_checksum(path: Path) -> Path:
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum_path.write_text(
        f"{sha256_file(path)}  {path.name}\n",
        encoding="ascii",
    )
    return checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create clean public and source release ZIPs")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--binary-root", type=Path)
    parser.add_argument("--release-root", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signature-status", default="Unknown")
    parser.add_argument(
        "--verify-source-only",
        action="store_true",
        help="verify the canonical source manifest and build a temporary source stage",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    version = args.version.strip()
    if args.verify_source_only:
        source_stage = project_root / "pab_source_stage"
        try:
            build_source_stage(project_root, source_stage, version)
        finally:
            remove_tree(source_stage)
        print("Source manifest and clean source-stage verification: PASS")
        return 0

    if args.binary_root is None or args.release_root is None:
        parser.error("--binary-root and --release-root are required unless --verify-source-only is used")
    binary_root = args.binary_root.resolve()
    release_root = args.release_root.resolve()
    release_root.mkdir(parents=True, exist_ok=True)

    validate_public_binary(binary_root, version)

    source_stage = project_root / "pab_source_stage"
    source_root = build_source_stage(project_root, source_stage, version)

    binary_name = f"PortableAccountBrowser_Windows_x64_v{version}_Public.zip"
    source_name = f"PortableAccountBrowser_Source_v{version}.zip"
    binary_zip = release_root / binary_name
    source_zip = release_root / source_name

    zip_tree(
        binary_root,
        binary_zip,
        f"PortableAccountBrowser_Windows_x64_v{version}",
    )
    zip_tree(source_root, source_zip, source_root.name)

    validate_zip(
        binary_zip,
        (
            "/PortableAccountBrowser.exe",
            "/runtime/chromium/chrome.exe",
            "/PORTABLE_BUILD_MODE.txt",
            "/README.md",
        ),
        minimum_files=100,
    )
    validate_zip(
        source_zip,
        (
            "/app.py",
            "/epb/browser.py",
            "/scripts/build_publish_release.ps1",
            "/README.md",
            "/LICENSE",
            "/SOURCE_MANIFEST.sha256",
        ),
        minimum_files=65,
    )

    binary_checksum = write_checksum(binary_zip)
    source_checksum = write_checksum(source_zip)
    sums_path = release_root / f"SHA256SUMS_v{version}.txt"
    sums_path.write_text(
        binary_checksum.read_text(encoding="ascii")
        + source_checksum.read_text(encoding="ascii"),
        encoding="ascii",
    )

    report = release_root / f"BUILD_REPORT_v{version}.txt"
    report.write_text(
        "\n".join(
            (
                f"Portable Account Browser v{version}",
                "Release type: clean public binary + complete open-source source",
                f"Binary ZIP: {binary_name}",
                f"Binary ZIP SHA-256: {sha256_file(binary_zip)}",
                f"Source ZIP: {source_name}",
                f"Source ZIP SHA-256: {sha256_file(source_zip)}",
                f"Authenticode: {args.signature_status}",
                "Personal profiles/cookies/sessions included: NO",
                "Source archive completeness validation: PASS",
                "ZIP CRC validation: PASS",
                "Sensitive-data leakage scan: PASS",
                "Release-root write test: PASS",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"PUBLIC_BINARY_ZIP={binary_zip}")
    print(f"SOURCE_ZIP={source_zip}")
    print(f"SHA256SUMS={sums_path}")
    print(f"BUILD_REPORT={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
