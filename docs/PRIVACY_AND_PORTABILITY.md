# Privacy and Portability

## Local storage

Portable Account Browser stores profile metadata and Chromium user-data files
inside the extracted application folder. The launcher does not implement
telemetry or a remote account service.

## Password handling

Passwords are entered directly on Gmail, Outlook, WhatsApp Web, Telegram Web,
or another provider website. The launcher does not provide a password field
and does not intentionally collect account passwords.

## Session persistence

Chromium profile files can preserve cookies, Local Storage, IndexedDB, service
workers, and preferences. Providers may still request login or MFA after
security changes.

## Device portability boundary

The application folder is portable. Existing authenticated sessions are not
guaranteed to work under another Windows user or computer because browser
encryption and provider risk checks may be tied to the operating-system
account, device, IP address, or security environment.

## Public-release safety

Official public release generation excludes:

- profile databases;
- cookies;
- login databases;
- browser history;
- Local Storage and IndexedDB;
- personal downloads;
- logs;
- update backups.

Never publish a personal build or a ZIP containing authenticated profiles.
