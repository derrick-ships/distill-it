# Domain: app-management

Patterns for managing a portfolio of generated or user-created projects within a single builder tool — including project scaffolding, process lifecycle, collections/grouping, commit-keyed thumbnails, bulk operations, and multi-backend file search.

## What this domain is about

When a tool can generate multiple standalone projects, you need a home screen that's more than a file picker. App management covers the data model, UX patterns, and infrastructure for treating each project as a first-class object: created from templates, organized into groups, searchable by code content, run as independent processes, and visually represented by thumbnails that stay accurate to the code state.

## Core patterns

- **Git init on create:** Every new project gets a git repository initialized automatically. This enables versioning, diff views, and commit-keyed thumbnails without user action.
- **Commit-keyed thumbnails:** Screenshots are saved using the git commit hash as the filename. This means thumbnails accurately reflect a specific code state and persist through reverts.
- **Process map for lifecycle:** Keep a `Map<projectId, ChildProcess>` to track running dev servers. Stop before delete, stop before restart. Retry filesystem cleanup on Windows (file locks).
- **Collections as soft-deleted folders:** Collections are DB rows with a `deletedAt` column. App membership is a nullable FK. Supports orphan-on-delete or cascade-delete.
- **ripgrep for code search:** Searching file *contents* (not names) across a large project is orders of magnitude faster with ripgrep than Node's `fs` module. Bundle `rg` with the app.
- **Client-side app filtering + server-side content search:** Filter app names client-side as the user types; use SQL `LIKE` or ripgrep for full content search across chats and files.

## Features in this domain

- [[multi-app-library--from-dyad]] — Full multi-project management in a local AI builder: SQLite data model, template scaffold, process lifecycle, commit-keyed thumbnails, collections, ripgrep search
