from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(zip_path: Path) -> None:
    checksum_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    if not checksum_path.is_file():
        raise RuntimeError(f"Missing checksum: {checksum_path}")
    parts = checksum_path.read_text(encoding="ascii").strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != sha256_file(zip_path):
        raise RuntimeError(f"Checksum mismatch: {zip_path.name}")


def verify_zip(zip_path: Path, required: tuple[str, ...], minimum_files: int) -> None:
    if not zip_path.is_file():
        raise RuntimeError(f"Missing ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"CRC failure in {zip_path.name}: {bad}")
        names = archive.namelist()
        file_count = sum(not name.endswith("/") for name in names)
        if file_count < minimum_files:
            raise RuntimeError(f"Archive too small: {zip_path.name} ({file_count} files)")
        for suffix in required:
            if not any(name.endswith(suffix) for name in names):
                raise RuntimeError(f"Missing {suffix} in {zip_path.name}")

        lower_names = [name.casefold() for name in names]
        forbidden = (
            "/data/profiles.sqlite3",
            "/cookies",
            "/login data",
            "/data/ui_settings.json",
            "/data/update_backups/",
        )
        if "_public.zip" in zip_path.name.casefold():
            for marker in forbidden:
                if any(marker in name for name in lower_names):
                    raise RuntimeError(f"Sensitive item detected in public ZIP: {marker}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    root = args.release_root.resolve()
    version = args.version
    binary = root / f"PortableAccountBrowser_Windows_x64_v{version}_Public.zip"
    source = root / f"PortableAccountBrowser_Source_v{version}.zip"

    verify_zip(binary, ("/PortableAccountBrowser.exe", "/runtime/chromium/chrome.exe"), 100)
    verify_zip(source, ("/app.py", "/epb/browser.py", "/LICENSE", "/README.md"), 65)
    verify_checksum(binary)
    verify_checksum(source)

    print("Publish release verification: PASS")
    print(f"Binary: {binary}")
    print(f"Source: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
