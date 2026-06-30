# Contributing

Contributions are welcome when they preserve existing behavior, portability,
session isolation, security, and backward compatibility.

## Development setup

```bat
setup_dev.bat -Python "D:\App\python312\python.exe"
test_dev.bat
run_dev.bat
```

## Pull-request requirements

- Keep all existing supported providers unless removal is explicitly approved.
- Add or update tests for every behavior change.
- Run the complete test suite before submitting.
- Do not commit personal profiles, cookies, browser databases, tokens, logs,
  downloads, `.venv`, packaged Chromium, or generated release ZIP files.
- Keep network destinations explicit and HTTPS-only for custom services.
- Update README, CHANGELOG, and security documentation where applicable.

## Coding standards

- Python 3.10+ compatible code.
- Type hints for public interfaces.
- Clear exception handling and actionable error messages.
- No placeholder implementations or silent failure paths.
- Avoid UI-thread blocking operations.
- Preserve app-local portable paths.

## Commit style

Use concise imperative messages, for example:

- `Fix single-tab session restoration`
- `Add provider validation tests`
- `Document portable-cookie limitations`

By contributing, you agree that your contribution is licensed under the MIT License.
