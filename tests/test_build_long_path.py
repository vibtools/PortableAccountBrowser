from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_portable.ps1"


def test_build_uses_short_portable_staging_path() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '$PyInstallerDistRoot = Join-Path $ProjectRoot "dist\\PortableAccountBrowser"' in text
    assert '$DistRoot = Join-Path $ProjectRoot "pab"' in text
    assert 'Move-Item -LiteralPath $PyInstallerDistRoot -Destination $DistRoot' in text
    assert 'Remove-Item -Recurse -Force $DistRoot -ErrorAction SilentlyContinue' in text


def test_short_stage_is_used_for_runtime_and_personal_data() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '$PortableRuntime = Join-Path $DistRoot "runtime\\chromium"' in text
    assert 'Join-Path $DistRoot "data\\profiles"' in text
    assert 'Join-Path $DistRoot "data\\downloads"' in text
