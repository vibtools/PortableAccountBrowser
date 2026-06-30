# Forensic Audit Report — v1.3.1

## Scope

- Python syntax and imports
- Existing profile/session behavior
- Build-process detection
- PyInstaller metadata/icon/manifest integration
- Public-data exclusion
- Source archive completeness
- ZIP CRC and SHA-256 verification
- Release directory write permissions
- GitHub documentation and license files

## Result

All existing functional tests pass. The release pipeline contains explicit gates that reject personal data and incomplete source archives. Windows EXE construction must be executed on Windows. Authenticode signing remains dependent on a publisher-owned certificate.
