# Domain: Adaptive Parsing

Features that make data extraction *survive change* — selectors, parsers, or extractors that
don't break the moment a source (a website, a document format, an API response shape) is
restructured. The common thread: instead of treating a locator as a brittle exact string,
these features store enough about *what* they're looking for to re-find it by resemblance.

## Features in this domain
- [[adaptive-element-relocation--from-scrapling]] — fingerprint an HTML element, re-find it by
  fuzzy similarity when its CSS/XPath selector later breaks. (from Scrapling)

## Why this domain matters
Maintenance is the hidden tax on any scraping or extraction system. Anything that reduces the
"the source changed, now my code is broken" loop is disproportionately valuable. When studying
a new repo, anything resembling self-healing extraction belongs here.
