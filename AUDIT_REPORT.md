# Forensic Audit Report — v1.3.1

Audit date: 2026-08-20
Initial target: commit `9c89d8f`
Frozen remediation baseline: commit `27aec9e`

## Executive summary

The application has a small, understandable attack surface: a local Tk launcher, SQLite
metadata, and a separately bundled Chromium runtime. Automated tests pass and the code uses
parameterized SQL, direct argument-vector process launches, HTTPS-only custom URLs, confined
profile identifiers, and explicit public-release data checks.

The audit found **three medium-severity release-integrity weaknesses** and **one low-severity
quality issue**. All four are remediated in the audited tree:

1. A top-level source input implemented as a symbolic link could be dereferenced and copied
   into a source release. Source inputs now reject symbolic links before copying.
2. Source-stage validation did not reject Chromium credential/session filenames or unexpected
   files under `data/`. It now applies sensitive-name and public-data allow-list checks to the
   source stage, not only to the binary stage.
3. The release packager imported an unused standard-library module; the import was removed so
   the repository passes Ruff.
4. A follow-up forensic review of PR #7 found that its symlink control covered top-level files
   and directory descendants, but not a selected source directory itself. The shared directory
   copy boundary now rejects a symbolic-link root before traversal.

No embedded credentials, populated profile directories, cookie databases, or account data were
found in the tracked working tree. This is a source-level audit, not a guarantee about a future
Chromium bundle or Windows binary.

## Scope and method

- Reviewed all Python application, packaging, and verification code.
- Reviewed dependency pins and the Windows CI/build entry points.
- Searched tracked content for credential markers, unsafe process execution, dynamic execution,
  insecure URLs, and generated/private browser artifacts.
- Inspected the tracked `data/` and `runtime/` trees for non-placeholder content.
- Ran the complete test suite, Ruff, byte-code compilation, dependency consistency checks,
  Git object integrity checks, and source-stage construction.
- Added regression coverage for both release-integrity findings.

## Findings and disposition

### FA-01 — Source input symlink dereference (Medium, fixed)

`copy_source_directory` already rejected links inside copied directories, but `copy_file` did not.
Consequently, a named top-level release input such as `README.md` could be replaced by a symlink
and its target copied by `shutil.copy2`. The packager now rejects every symlink at the common
file-copy boundary. A regression test demonstrates rejection before staging.

### FA-02 — Source archive could contain browser/account data (Medium, fixed)

The clean binary validator rejected non-placeholder files below `data/` and known Chromium
sensitive filenames. Equivalent checks were absent from `validate_source_stage`, even though the
source builder recursively copies selected directories. Source validation now rejects known
cookie, login, history, preference, token-state, and application database filenames anywhere in
the stage, and permits only placeholder files under staged `data/`.

This is defense in depth rather than content inspection. Renamed or encrypted private files
cannot be identified reliably by filename scanning; release operators must still build from a
reviewed, clean checkout.

### FA-03 — Ruff unused import (Low, fixed)

`scripts/package_publish_release.py` imported `tempfile` without using it. Removal restores a
clean static-quality check.

### FA-04 — Top-level source directory symlink bypass (Medium, fixed)

The PR #7 fix rejected symbolic links in `copy_file` and while iterating directory descendants,
but `copy_source_directory` did not inspect its `source` argument. Since `Path.is_dir()` follows
links, a selected source directory such as `assets/` could itself be replaced by a link to an
external directory and its regular-file descendants copied into the source release. The copy
boundary now rejects a linked directory root before traversal, with a regression test proving
that the external file is not staged.

## Positive controls observed

- SQLite statements that include user/profile values use parameters rather than string-built SQL.
- Profile IDs are generated as lowercase UUID hex and validated before becoming directory names.
- Managed browser directories are resolved and checked against the portable application root.
- Chromium is launched without a shell, using a list of arguments.
- Custom launch URLs require HTTPS, a hostname, no embedded credentials, no control characters,
  a valid port, and a maximum length.
- Public binary validation rejects all non-placeholder files in application data directories and
  scans the full package for known sensitive browser filenames.
- Release archives receive CRC validation and SHA-256 sidecar checksums.
- The repository contains only placeholder files under tracked `data/` and `runtime/chromium/`.

## Residual risk and limitations

- **Bundled Chromium:** the browser binary is not present in this source checkout. Its provenance,
  code signature, version, CVEs, and file inventory must be verified on the Windows release host.
- **Dependency vulnerabilities:** installed-package consistency was checked, but `pip-audit` was
  unavailable in the audit environment. CI should add an authenticated or network-capable
  dependency vulnerability scan.
- **Windows-only behavior:** native process enumeration, AppUserModelID/DWM calls, PyInstaller
  output, Authenticode signing, and the complete PowerShell release flow were not executable on
  this Linux host.
- **At-rest secrets:** Chromium profile cookies remain portable application data. Depending on
  Chromium/Windows cryptography and the identity provider, portability and confidentiality can
  vary. Users must protect the portable folder as sensitive material.
- **Checksums are not signatures:** SHA-256 detects accidental or post-publication changes only
  when obtained from a trusted channel. Authenticode and signed release attestations remain the
  publisher's responsibility.
- **Filename scanning:** release leakage checks prevent common browser artifacts but cannot prove
  arbitrary files contain no sensitive content. Human review and clean-checkout builds remain
  required.

## Release recommendation

The source is suitable to proceed to the Windows release-validation stage after these fixes.
Do not publish a binary until the bundled Chromium inventory and signature, PyInstaller output,
full PowerShell verifier, ZIP checksums, malware scan, and Authenticode status have been verified
on the intended Windows build host.
