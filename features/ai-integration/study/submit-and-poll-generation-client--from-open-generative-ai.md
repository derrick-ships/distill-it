# Submit-and-Poll Generation Client — from [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI)

> Domain: [[_domain]] · Source: https://github.com/Anil-matcha/Open-Generative-AI · NotebookLM: <add link>

## What it does
This is the single piece of machinery that turns "click Generate" into a finished image or video, no matter which of the 200+ models you picked. You send the request, the system gets back a ticket number, and then it quietly checks "is it done yet?" every couple of seconds until the result is ready — then hands you back one clean link to the output. Every studio in the app (image, video, image-to-video, lip-sync, audio, ads) runs through this exact same mechanism.

## Why it exists
AI generation is slow and unpredictable — an image might take 10 seconds, a video might take 8 minutes. You can't hold an HTTP connection open that long, and you can't make the user stare at a frozen button. The job-to-be-done is **"start a long task, survive the wait, and reliably know when it finished or failed"** — for every model, with one piece of code instead of a hundred. The payoff is huge leverage: adding a brand-new model is just a new entry in a list, because the waiting logic is already written once and shared by everyone.

## How it actually works
There are really just two moving parts:

1. **Submit.** It posts your request (prompt, aspect ratio, etc.) to the model's endpoint with your API key attached. The server doesn't return a picture — it returns a *ticket*, a `request_id`. (Clever touch: if the server happens to answer instantly with the actual result and no ticket, the code notices there's no ticket and just hands that back directly. Fast models don't pay the polling tax.)

2. **Poll.** Holding the ticket, it asks a "what's the status of this ticket?" endpoint over and over, waiting two seconds between each check. It's looking for three words in the reply: if the status is *completed/succeeded/success*, it's done; if it's *failed/error*, it gives up with a clear message; anything else (queued, processing) means "keep waiting." Each task type gets a budget — images wait up to ~2 minutes, videos up to ~30 minutes — after which it declares a timeout.

The last nice bit: different models phrase their answer differently — some return `outputs: [url]`, some `url`, some `output.url`. The code checks all three and collapses them into one field, so the rest of the app only ever has to read a single `.url`.

## The non-obvious parts
- **It waits *before* the first check, not after.** Polling instantly at t=0 is pointless — the job can't be done yet — and just wastes a request. Sleeping first is a small, smart politeness.
- **Server errors and client errors are treated oppositely.** A 500 ("the server hiccuped") is shrugged off and polling continues; a 400/401/403 ("you did something wrong") stops immediately. Getting this backwards would either make it spin forever on a real failure or quit on a momentary blip.
- **It tolerates flakiness.** A dropped connection mid-wait doesn't kill the job — errors are swallowed until the very last attempt. The generation is resilient to a bad Wi-Fi moment.
- **The "ticket number" is also a UX hook.** The moment a ticket comes back, it's handed to the UI (`onRequestId`) — that's what powers progress indicators, history entries, and "stop watching this one."
- **The real lesson isn't the code, it's the shape.** This is the universal pattern for wrapping *any* async AI gateway (Replicate, fal, Muapi, etc.). Write submit+poll once; every model becomes a five-line payload builder.

## Related
- [[centralized-model-registry--from-open-generative-ai]] — supplies the per-model `endpoint` that this client submits to.
- [[browser-host-api-proxy--from-open-generative-ai]] — explains the `/api` vs direct-host base URL and where the API key actually gets injected.
- [[multi-studio-shell-architecture--from-open-generative-ai]] — the UI that calls these generate functions and consumes the normalized `.url`.
- See also: [[provider-agnostic-llm--from-llm-scraper]] — a different take on multi-model support: abstract above the vendor via an SDK, vs. here, normalize a single gateway's async protocol.
