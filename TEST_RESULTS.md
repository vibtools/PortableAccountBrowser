# Test Results — v1.3.1

- Python compilation: PASS
- Automated unit/regression tests: 56/56 PASS
- Ruff static analysis: PASS
- Source package required-file validation: PASS
- Public binary sensitive-data scanner tests: PASS
- Build-process self-detection regression: PASS
- Version/icon/release asset checks: PASS
- Linux-side source test run: PASS

Latest source verification: 2026-08-20 on Linux with Python 3.14.4 and Ruff 0.15.12.

Final PyInstaller, Windows ACL, Authenticode status, Chromium runtime, and packaged executable
diagnostics must still be verified by `build_publish_ready.bat` on the target Windows PC. An
unsigned build is supported, but its build report must record the non-valid signature status.
