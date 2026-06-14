# YouTube URL Extraction — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Converts a YouTube watch URL into a Markdown document containing the video's title, metadata (views, keywords, duration), description, and full transcript. The result is a complete, text-readable version of a YouTube video — useful for feeding video content to LLMs without any video processing.

## Why it exists

YouTube is a massive repository of knowledge — tutorials, lectures, interviews, conference talks — that's inaccessible to text-only LLMs. Converting a YouTube URL to Markdown (with transcript) makes that content directly usable in any text pipeline.

## How it actually works

**URL detection:** The converter checks whether the stream's URL starts with `https://www.youtube.com/watch?`. It's triggered as part of the HTML converter path — the URL is fetched as HTML first, and the YouTubeConverter intercepts based on the URL pattern.

**Metadata scraping:** The fetched HTML is parsed with BeautifulSoup. The converter extracts metadata from `<meta>` tags: `interactionCount` (views), `keywords`, `duration`. The video title comes from the page `<title>` tag (with ` - YouTube` stripped).

**Description extraction:** YouTube embeds the description inside a `<script>` tag containing a large JSON blob named `ytInitialData`. The converter finds this script, extracts the JSON, and recursively searches for the `attributedDescriptionBodyText` field, which contains the full video description.

**Transcript retrieval:** Using the optional `youtube_transcript_api` library, the converter:
1. Extracts the video ID from the URL's `v=` parameter.
2. Lists available transcript languages.
3. Fetches transcripts with retry logic — up to 3 attempts with 2-second delays between failures.
4. Falls back to auto-translated transcripts if the preferred language isn't available.
5. Joins all transcript segments into a continuous text block.

**Output:** A structured Markdown document: title as `#` heading, metadata as key-value pairs, description section, and transcript section.

## The non-obvious parts

- `youtube_transcript_api` is optional. Without it, the converter produces title + metadata + description only, with no transcript.
- The description is NOT in a simple meta tag — it's buried in a multi-megabyte JSON blob inside a script tag. The recursive search is necessary because the JSON structure changes across YouTube UI versions.
- Retry logic (3 attempts, 2s delay) exists because YouTube's transcript endpoint is rate-limited and occasionally flaky.
- This converter only handles `youtube.com/watch?` URLs — not Shorts, channel pages, or playlists.

## Related

- [[html-web-conversion--from-markitdown]] — the generic HTML path that YouTube overrides
- [[converter-pipeline--from-markitdown]] — dispatches based on URL detection
