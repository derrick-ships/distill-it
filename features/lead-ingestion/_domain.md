# Domain: lead-ingestion

Getting leads/contacts *into* the system from the outside world — web forms, automation tools, batch
files — with as little friction as possible and tolerant of messy, inconsistent payloads.

## What this domain is about

Lead ingestion is the **front door**: the moment a prospect raises their hand (submits a form, gets
imported from a list), they should land in the CRM automatically. The hard parts aren't the insert —
they're tolerating the chaos of real-world inputs: arbitrary field names across languages and form
builders, nested vs flat payloads, partial data, and untrusted callers. A good ingestion layer
absorbs that mess so the rest of the system sees clean, normalized records.

## Pattern shared across features in this domain

Normalize → map → default → insert. Incoming keys are normalized (lowercase/trim/underscore),
nested structures flattened, then a **field-alias dictionary** maps many possible input names onto a
small set of canonical fields. Only a minimal field (a name) is required; everything else defaults
(source, temperature, score, timestamps). Newly ingested leads land *unscored* — scoring/
classification is a deliberately separate step. Endpoints favor partial success and helpful error
echoes (return the keys received) because integrations are debugged blind.

## Features in this domain

- [[webhook-lead-ingestion--from-auto-crm]] — a public POST endpoint that maps multilingual/Typeform
  field names to a contact, optional shared-secret auth, name-required, defaults to webhook/cold/0,
  no dedup by design.
