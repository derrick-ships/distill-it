# Background Command Scheduling — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Extension commands in Asyar can declare a `@schedule` in their manifest to run automatically at a fixed interval — without any user action. For example, an extension might fetch stock prices every 60 seconds, sync a todo list every 5 minutes, or check system health every 10 minutes. Asyar's scheduler wakes the extension's background worker at each interval and delivers the command message.

## Why it exists

Launchers traditionally require user initiation. Scheduling turns the launcher into a persistent automation runtime: extensions become background daemons that can update data, trigger notifications, or run maintenance tasks continuously while the user does other things.

## How it actually works

**Scheduler state**: The Rust `SchedulerState` struct holds a `HashMap<String, JoinHandle>` protected by a `Mutex`. Keys are `"extensionId::commandId"` pairs. Values are `tokio::task::JoinHandle` — one per scheduled command. This allows starting, stopping, and querying tasks by key.

**Interval validation**: Declared intervals must be between **10 seconds and 86,400 seconds (24 hours)**. The `validate_interval()` function enforces these bounds. Intervals outside this range are rejected at enable-time.

**Startup**: When the app starts (and on extension enable), `start_all_tasks()` iterates every enabled extension, inspects each command's manifest for a schedule definition, validates the interval, and spawns a tokio interval task for each match.

**Timer loop**: Each spawned task creates a `tokio::time::interval` and enters a loop. The first tick is **skipped** (tokio intervals fire immediately by default — skipping avoids running the command at startup before the extension's worker iframe is ready). On each subsequent tick, the scheduler:
1. Builds a `PendingMessage { kind: MessageKind::Command, commandId }` 
2. Calls `mgr.enqueue_worker(extensionId, message)` which returns a `DispatchOutcome`
3. Emits a Tauri event based on the outcome:
   - `ReadyDeliverNow` → emits `EVENT_DELIVER` (worker is running, message delivered instantly)
   - `NeedsMount` → emits `EVENT_MOUNT` (worker iframe needs to be created first)
   - `Degraded` / `MountingWaitForReady` → logged but no event (transient state, next tick will retry)

**Worker iframe lifecycle**: Extensions have a "worker" iframe that runs their background JavaScript. This iframe can be auto-mounted at startup (if the extension declares `background.main`). The scheduler is resilient to the worker not being mounted — the `NeedsMount` outcome signals the frontend to create the iframe, after which the message is delivered.

**Stopping tasks**: `stop_task(key)` aborts the `JoinHandle` for a specific `"extensionId::commandId"`. This is called when an extension is disabled or uninstalled. Cleanup is immediate — no orphaned timer fires.

## The non-obvious parts

**Skip-first-tick**: Tokio intervals fire immediately at t=0. For the scheduler, this is undesirable — the extension's worker might not be mounted yet. Skipping the first tick gives the system time to initialize before the first scheduled run.

**Resilient delivery**: The scheduler doesn't fail if the worker isn't running. It emits `EVENT_MOUNT` instead, letting the frontend mount the iframe. The next tick (after mount + ready) will find `ReadyDeliverNow` and deliver normally. This decouples the scheduler from the extension lifecycle.

**Task map as the source of truth**: The `HashMap<key, JoinHandle>` is the authoritative list of what's currently scheduled. Extensions can be dynamically enabled/disabled at runtime — the task map is updated accordingly.

**No persistence**: Scheduled tasks are ephemeral — they exist only while the app is running. There's no "catch-up" for missed intervals while the app was closed. This is intentional: scheduled extensions are designed for polling, not for guaranteed delivery.

## Related

- [[sandboxed-extension-system--from-asyar]] (scheduled commands run inside extension worker iframes)
- [[deep-link-command-triggers--from-asyar]] (another way to trigger extension commands externally)
- [[command-palette-launcher--from-asyar]] (the same extension commands can also be triggered manually)
