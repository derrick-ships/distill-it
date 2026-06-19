# Async-to-Sync Status Bridging — from [PermissionsKit](https://github.com/sparrowcode/PermissionsKit)

> Domain: [[_domain]] · Source: https://github.com/sparrowcode/PermissionsKit · NotebookLM: <link once added>

## What it does

PermissionsKit promises that you can check any permission's status by reading a plain property — `Permission.notification.status` — and get an answer *right now*, synchronously. The problem: Apple doesn't let you. For notifications, the only way to learn the status is an asynchronous callback (`getNotificationSettings` hands you the answer later, on a background queue). For location, the answer arrives even more indirectly, through a delegate object.

This feature is the small, sharp trick that squares that circle: it makes an inherently asynchronous answer *look* synchronous, so the whole library can keep its clean "just read the property" promise. It's a reusable Swift concurrency-bridging pattern that shows up far beyond permissions.

## Why it exists

A consistent API is the entire value proposition of PermissionsKit. If 16 permissions let you read `status` instantly but two of them forced you to write callback code, the abstraction would leak — and a leaky abstraction is almost worse than none, because you can't trust the uniform interface. So the library pays a cost (blocking a thread briefly) to preserve the promise (uniform, synchronous status everywhere). It's a deliberate trade: a little blocking in exchange for an API that never surprises you.

## How it actually works

The tool is a **`DispatchSemaphore`** — a counter you can wait on. The pattern, for notifications, is:

1. Create a semaphore starting at zero. A zero semaphore means "anyone who waits on me blocks until someone signals."
2. Kick off Apple's async call on a background queue. Inside its completion callback — whenever it eventually fires — capture the result into a variable and then **signal** the semaphore (bump the counter to one).
3. Immediately after kicking it off, call **wait** on the semaphore. Because it started at zero, the current thread parks here, doing nothing, until step 2 signals it.
4. Once signaled, `wait` returns, and the captured result is now sitting in the variable, ready to return synchronously.

From the caller's point of view, they called a normal function and got a normal return value. Under the hood, the thread briefly slept until Apple's callback delivered the answer. The async-ness is real but invisible.

Two details make it safe:

- **The async work runs on a background queue (`DispatchQueue.global()`), not the calling thread.** This matters enormously. If you fired the async call on the same thread you then block with `wait`, and Apple happened to deliver the callback on *that* thread, you'd deadlock forever — the thread can't run the callback because it's parked waiting for the callback. Pushing the async work to a *different* queue guarantees the signal can fire even while the original thread sleeps.
- **The result variable is written in the callback and read after `wait` returns** — and the `wait`/`signal` handshake creates the memory ordering that makes that safe (the read is guaranteed to see the write).

Location uses a *sibling* of this pattern rather than the semaphore directly. Location authorization only comes back through a `CLLocationManager` delegate, and a delegate object will be deallocated the instant nothing holds a strong reference to it — which would kill the request mid-flight. So the location code parks its handler in a **static `shared` property** (`LocationWhenInUseHandler.shared = …`), which keeps it alive for the duration of the async request, then sets that property back to `nil` inside the completion to let it deallocate. Same underlying problem — "bridge an async/delegate answer into our synchronous, uniform world" — solved with a lifetime anchor instead of a semaphore.

## The non-obvious parts

- **Blocking a thread on purpose is the whole point — and it's a controlled risk.** Most Swift guidance screams "never block." Here it's a conscious, bounded choice: the block lasts only as long as a cheap system query, and it buys a dramatically simpler public API. The lesson isn't "block threads," it's "know exactly when a tiny block is worth a big ergonomic win."
- **The background-queue dispatch is load-bearing, not incidental.** It looks like a stylistic choice but it's the deadlock guard. Dispatch the async call to the *same* place you wait and you can hang the app. This is the single easiest thing to get wrong when copying the pattern.
- **`status` should never be read on the main thread in a hot path.** Because it can block, calling it on the main thread stutters the UI if the system query is slow. The safe move is to read status off-main (or cache it), even though the API makes it tempting to sprinkle everywhere.
- **Two different mechanisms for the same job.** Notifications use a semaphore; location uses a static-property lifetime anchor. They look unrelated but they're answers to the same question — "how do I turn Apple's deferred answer into my synchronous one?" — and which one you reach for depends on whether the API is callback-based (semaphore) or delegate-based (keep the delegate alive).
- **It's a general pattern, not a permissions thing.** Any time you must expose a synchronous getter over an async-only system API (settings reads, capability checks, one-shot queries), this is the shape. Permissions is just where it happens to live here.

## Related

- [[unified-permission-abstraction--from-permissionskit]] — this bridge is *why* that abstraction can present `status` as one uniform property across all 18 permissions; it's the enabling mechanism.
- [[modular-permission-packaging--from-permissionskit]] — the bridging code ships inside the specific permission modules (notification, location) that need it.
