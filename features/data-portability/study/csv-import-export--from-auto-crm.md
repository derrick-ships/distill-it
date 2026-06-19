# CSV Import / Export — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/app/api/import/route.ts`, `src/app/api/export/route.ts`) · NotebookLM: <add link>

## What it does
The two doors that let your data walk in and out of the CRM. **Import** takes a batch of contacts
(an array of contact objects) and bulk-inserts them, reporting back exactly how many landed and which
ones failed and why. **Export** does the reverse: it pulls all your contacts (or all your deals) and
hands you a downloadable CSV file that opens cleanly in Excel — properly escaped, UTF-8, with the
right filename and a date stamp. Together they're the "no lock-in" promise made real: you can get
your data out any time, and seed the CRM from your old spreadsheet on day one.

## Why it exists
For a self-hosted CRM whose pitch is "you own your data," portability isn't a nice-to-have, it's the
whole brand. The job-to-be-done: **onboarding without retyping** (import the spreadsheet you already
have) and **trust through escapability** (you can always export everything, so you're never trapped).
The export side also doubles as ad-hoc reporting — hand a CSV to a manager or open it in Excel for a
pivot table the app doesn't provide.

## How it actually works
**Import** accepts a POST whose JSON body has a `contacts` array. (Note: the *parsing* of a raw CSV
file into that array happens on the client/before this endpoint — the server takes structured JSON,
not a raw .csv.) For each contact object it maps the obvious fields (name, email, phone, company,
source, temperature, score, notes) onto the database columns, filling defaults for anything missing:
source defaults to `"import"`, temperature to `"cold"`, score to `0`, timestamps to now. The one hard
rule is that each row needs a name; a row without one is counted as a failure (with a logged error
message) rather than aborting the whole batch. It tallies successes and failures independently and
returns `{ imported, failed, errors }` — with a 201 if everything succeeded and a **207
(Multi-Status)** if some rows failed but others made it. So a messy spreadsheet imports as much as it
can and tells you precisely what it couldn't.

**Export** is a GET with a `type` parameter (`contacts` or `deals`). For contacts it grabs all of
them newest-first and writes nine columns (name, email, phone, company, source, temperature, score,
notes, created date), translating the temperature codes into Spanish words ("Caliente"/"Tibio"/
"Frío") for human readability. For deals it joins each deal to its contact and stage and writes eight
columns (title, currency-formatted value, contact name, stage, probability, expected close, notes,
created date). A small `buildCSV` helper does the careful part: every value is run through an
`escapeCSV` that wraps anything containing a comma, quote, or newline in double-quotes and doubles
internal quotes — the standard CSV escaping that keeps a note like `Said "yes, maybe"` from blowing
up the columns. The response is sent as `text/csv; charset=utf-8` with a **UTF-8 BOM prefix** (so
Excel doesn't mangle accented characters), a `Content-Disposition: attachment` to trigger a download,
and a dated filename like `contactos-2026-06-18.csv`.

## The non-obvious parts
- **Import is partial-success by design.** It never all-or-nothing aborts; it imports every valid row
  and returns a per-row error list, signalled by the 207 status. This is the right behavior for human
  spreadsheets where a few rows are always malformed.
- **The server imports JSON, not CSV.** The actual CSV→objects parsing lives client-side; the
  endpoint is a structured bulk-insert. A porting gotcha — don't expect to POST a raw file here.
- **The UTF-8 BOM is a deliberate Excel hack.** Without `﻿` at the front, Excel guesses the
  encoding wrong and turns "Frío" into "FrÃ­o". One invisible character saves a thousand support
  tickets. Easy to forget, very visible when missing.
- **Export humanizes on the way out.** Temperature codes become Spanish words and deal values become
  formatted currency — the CSV is meant for a human in Excel, not a machine round-trip. (That means
  re-importing an export isn't lossless; "Caliente" won't map back to `"hot"` automatically.)
- **Proper CSV escaping is the unglamorous core.** The whole feature lives or dies on `escapeCSV`
  handling commas/quotes/newlines correctly; getting this wrong is the classic CSV bug.
- **Two entity types, one endpoint, switched by `type`.** Contacts and deals share the export route
  and the `buildCSV`/`escapeCSV` machinery; only the column set and the source query differ.

## Related
- [[webhook-lead-ingestion--from-auto-crm]] — the real-time, one-at-a-time cousin of batch import;
  both fill contacts with default values.
- [[rule-based-lead-scoring--from-auto-crm]] — imported contacts arrive at score 0 unless a score is
  provided; run scoring afterward to make them useful in the queue.
- See also: any "export to CSV / import from CSV" feature — the BOM + escape + partial-success
  patterns here are the reusable, get-them-right parts.
