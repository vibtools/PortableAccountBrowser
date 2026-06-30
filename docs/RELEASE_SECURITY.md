# Public Release Security

Only the clean public ZIP is safe to publish. The release builder rejects:

- `profiles.sqlite3`
- Chromium Cookies and Login Data files
- Local profile contents
- UI settings and update backups
- personal downloads and logs

Never publish a package produced by `build_personal_portable.bat`.
