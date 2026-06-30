# Security Policy

## Supported version

| Version | Supported |
|---|---|
| 1.3.1 | Yes |
| Older releases | Security fixes are not guaranteed |

## Reporting a vulnerability

Do not publish cookies, tokens, account identifiers, profile folders, or
reproduction archives containing personal data in a public issue.

Report security vulnerabilities through GitHub's private security-advisory
feature for this repository. Include:

- affected version;
- Windows version;
- impact;
- minimal reproduction steps;
- proposed mitigation, when available.

## Security model

- Passwords are entered on provider websites, not into the launcher.
- Account profiles are local files inside the portable application directory.
- The public release process rejects saved profiles, cookies, login databases,
  history, logs, and personal downloads.
- Release ZIP files are accompanied by SHA-256 checksums.
- Unsigned community builds may trigger Windows SmartScreen warnings.

See `docs/PRIVACY_AND_PORTABILITY.md` for portability boundaries.

