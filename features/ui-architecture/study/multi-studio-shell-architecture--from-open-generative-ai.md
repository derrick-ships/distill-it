# Multi-Studio Shell Architecture — from [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI)

> Domain: [[_domain]] · Source: https://github.com/Anil-matcha/Open-Generative-AI · NotebookLM: <add link>

## What it does
This is the skeleton that lets one app contain a dozen different "studios" — Image, Video, Lip Sync, Cinema, Workflow, Audio, and more — behind a simple row of tabs, and lets that exact same app ship both as a website and as a downloadable desktop program. You click a tab, the matching studio appears; everything around it (your API key, your balance, drag-and-drop) stays put. Under the hood, all the studios come from one shared toolbox that both versions of the app plug into.

## Why it exists
A product with twelve features can be built twelve times over — twelve screens, twelve setups, twelve copies of the "enter your key" logic — and become unmaintainable. And shipping the same product as both a web app and a desktop app usually means maintaining two front-ends. The job-to-be-done is **"add features cheaply and ship to multiple platforms from one codebase."** The answer is a thin, generic shell that hosts interchangeable feature modules, plus a single shared library that both the web and desktop builds consume without changes.

## How it actually works
Picture a power tool with swappable heads. The handle is always the same; you snap on whichever head you need.

- **The shared toolbox.** Every studio is built once and exported from a single file (a "barrel"). Both the website and the desktop app import from that one place, so there's exactly one copy of each feature, shared everywhere. The whole API layer rides along in the same package, so studios and the code that talks to the AI service always travel together.

- **The shell (the handle).** One component holds everything the studios have in common: your API key, your account balance (refreshed every 30 seconds), and the drag-and-drop files you drop onto the window. It shows a row of tabs, and when you pick one it simply mounts the matching studio and hands it the same small set of shared props. The shell also acts as a bouncer: if there's no API key, the *entire* app is replaced by the key-entry box — no key, no entry. And it listens for the app-wide "you're not authorized" signal; the instant that fires, it drops the key and the entry box reappears.

- **The studios (the heads).** Each studio is self-similar: it takes the same inputs (your key, any dropped files), reads the shared model catalog to draw its own controls, and calls the shared generation functions to do the work. They share behavior not by copying each other but by drawing from the same catalog and the same API layer.

- **The routing is almost nothing.** Because the shell does all the work, the web page that shows it is a two-line file, and the desktop app mounts the very same shell. The framework's own layout file is kept deliberately empty — all the real state lives in the shell, which is exactly what makes it portable between platforms.

## The non-obvious parts
- **Variation lives in data, the shell stays generic.** The differences between studios are pushed into a tab list, a model catalog, and a parameter schema — not into the shell. That's why adding a feature is "export a studio and add a tab," not "build a new screen." The shell never needs to change.
- **One uniform contract is what keeps the switch clean.** Every studio accepts the same handful of props, so the shell can mount any of them with identical code. The moment one studio demands something special, you're tempted to make the shell messy — the discipline is to feed special needs through the shared catalog instead.
- **All shared concerns live in one place, on purpose.** Auth, balance, drag-and-drop, the key modal — handled once by the shell, inherited by all twelve studios. The flip side is that the shell can grow into a "god component"; the architecture trades a little future risk for a lot of early simplicity.
- **Same code, two platforms, because state isn't tied to the framework.** By keeping the layout bare and the state in the shell, the team gets the desktop app almost for free — the renderer just mounts the same shell the website uses.
- **The auth gate is all-or-nothing.** Until you have a key, the whole app is the key box. It's a clean onboarding choice for a bring-your-own-key tool, but it bakes in an assumption: there's no anonymous browsing mode.

## Related
- [[centralized-model-registry--from-open-generative-ai]] — the catalog each studio reads to build its own form; the "data" that the generic shell defers to.
- [[submit-and-poll-generation-client--from-open-generative-ai]] — the shared generation functions every studio calls to do work.
- [[browser-host-api-proxy--from-open-generative-ai]] — the auth bridge whose `muapi:auth-required` signal the shell listens for, and the key the shell persists.
- See also: [[local-first-architecture--from-open-design]] and [[skills-system--from-open-design]] — other "thin core + interchangeable modules" structures to compare.
