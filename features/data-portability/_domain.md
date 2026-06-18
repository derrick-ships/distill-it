# Domain: data-portability

Getting data *out* of (and bulk *into*) a system in open, human-friendly formats — the "no lock-in"
promise made real, plus ad-hoc reporting via spreadsheets.

## What this domain is about

Data portability is **escapability and onboarding**: a user should be able to seed the tool from a
spreadsheet they already have and export everything back out any time. For a self-hosted, "you own
your data" product this isn't a feature, it's the brand. Export also doubles as the reporting the app
itself doesn't provide (open the CSV in Excel, pivot away).

## Pattern shared across features in this domain

Import is a **partial-success bulk insert**: loop rows, validate per-row (skip the bad, keep the
good), tally, and signal mixed results (HTTP 207) rather than all-or-nothing. Export builds CSV with
**correct escaping** (quote values containing comma/quote/newline, double internal quotes), a
**UTF-8 BOM** so Excel renders accents, humanized values for readability, and the right download
headers + dated filename. Server-side endpoints often take already-parsed JSON, with raw CSV parsing
done client-side.

## Features in this domain

- [[csv-import-export--from-auto-crm]] — partial-success JSON bulk import (201/207 + per-row errors)
  and dual contacts/deals CSV export (`escapeCSV`/`buildCSV`, UTF-8 BOM, humanized values, attachment
  download).
