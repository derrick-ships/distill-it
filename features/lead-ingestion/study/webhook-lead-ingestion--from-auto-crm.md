# Webhook Lead Ingestion — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/app/api/webhook/route.ts`) · NotebookLM: <add link>

## What it does
It's a single public URL you can point any web form, landing page, or automation tool at. When
someone fills out your "Contact us" form, that form's backend POSTs the submission as JSON to this
endpoint and a new contact instantly appears in the CRM — no manual data entry, no Zapier in the
middle. The clever part is that it doesn't demand a specific payload shape: it accepts both flat
forms and Typeform-style nested submissions, and it understands field names in multiple languages
and spellings (`name`, `nombre`, `full_name`, `email`, `correo`, …), so you can usually wire it up
without reformatting anything.

## Why it exists
The job-to-be-done is **zero-friction lead capture**: the moment a prospect raises their hand on a
website, they should already be in the pipeline. For a self-hosted, no-subscription CRM, paying for
a third-party form-to-CRM connector defeats the whole point — so the product ships its own webhook
receiver. The "accept many field names" design exists because the people wiring this up are often
non-technical or using a form builder they don't fully control; the endpoint absorbs the messiness
instead of forcing the user to produce a perfectly-named payload.

## How it actually works
The endpoint takes a POST with a JSON body. First it optionally checks security: if a webhook
secret has been configured in the CRM's settings, the request must carry a matching
`x-webhook-secret` header, otherwise it's rejected as unauthorized. If no secret is configured, the
endpoint is open (convenient, but worth knowing).

Then it normalizes. Every key in the incoming object is lowercased, trimmed, and has spaces turned
into underscores — so `"Full Name"`, `"full name"`, and `"full_name"` all collapse to the same key.
It also flattens Typeform-style nested structures so the real fields are reachable. Against this
normalized bag it runs a **field-mapping dictionary**: for each CRM field (name, email, phone,
company) it has a list of accepted aliases across languages (`name`/`nombre`/`full_name`,
`email`/`correo`/`e-mail`, `phone`/`telefono`/`tel`, `company`/`empresa`/`organizacion`) and picks
the first one present.

The only hard requirement is a name — if no name-like field is found, the request is rejected with
a 400 and (helpfully) a hint plus the list of keys it actually received, so whoever's debugging the
integration can see what came through. Everything else is optional. The new contact is created with
sensible defaults: source is set to `"webhook"`, temperature to `"cold"`, and score to `0`. On
success it returns 201 with the created contact's id, name, email, and source.

## The non-obvious parts
- **No deduplication, by design (or omission).** Every POST creates a brand-new contact, even if
  the same email already exists. Submit a form twice and you get two contacts. This is the single
  biggest gotcha — a noisy form or a retrying webhook sender will flood the CRM with duplicates.
- **No scoring on ingest.** Leads land at score 0 / cold and stay there until something *else* runs
  the classifier. The webhook's job is pure capture; grading is a separate step. If you never
  trigger classification, every webhook lead looks identically worthless.
- **Security is opt-in.** The secret check only happens if a secret was configured. An
  unconfigured endpoint is wide open to the internet — anyone who finds the URL can inject contacts.
- **The error response is a debugging aid.** Returning the received keys and a hint on a 400 is a
  deliberate developer-experience touch; webhook integrations are notoriously hard to debug blind,
  and most products give you a useless generic 400.
- **Normalization is forgiving but not magic.** It handles case, whitespace, underscores, common
  aliases, and one level of Typeform nesting — but a wildly custom payload still needs its field
  names added to the alias lists.

## Related
- [[rule-based-lead-scoring--from-auto-crm]] — the missing second half: webhook leads need this run
  against them to get a real score/temperature.
- [[csv-import-export--from-auto-crm]] — the batch cousin of this real-time capture path; both feed
  the contacts table with default-filled rows.
- See also: Typeform/Tally/Zapier webhooks — this endpoint is built to be their target without a
  paid connector in between.
