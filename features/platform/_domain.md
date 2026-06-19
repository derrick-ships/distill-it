# Domain: platform

Cross-cutting desktop-platform concerns: deep linking (custom URL schemes), background task scheduling, local data backup / restore with optional encryption, and OS-level integration that doesn't belong to a single product feature.

## Repos studied

- [[asyar]] — Tauri v2 local-first desktop launcher with `asyar://` scheme, tokio-based scheduler, and local encrypted backup

## Features in this domain

- [[deep-link-command-triggers--from-asyar]] — `asyar://` URL scheme for triggering any extension command from a browser or external app
- [[background-command-scheduling--from-asyar]] — Tokio-based scheduler that fires extension commands at declared intervals
- [[local-backup-restore--from-asyar]] — Local export/import of all user data with optional AES-256 password encryption
