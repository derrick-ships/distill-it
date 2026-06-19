# Background Command Scheduling (build spec) — distilled from asyar

## Summary

Tokio-based background scheduler that fires extension worker commands at declared intervals (10s–86400s). A `SchedulerState` mutex-guarded HashMap keyed on `"extId::cmdId"` holds live `JoinHandle`s. First tick is skipped; each subsequent tick enqueues a message to the extension worker and emits a Tauri event (`DELIVER` or `MOUNT`) for frontend routing. Tasks are started/stopped dynamically as extensions are enabled/disabled.

## Core logic (inlined)

### SchedulerState (Rust)
```rust
// extensions/scheduler.rs
use std::collections::HashMap;
use tokio::task::JoinHandle;
use tokio::sync::Mutex;

pub struct SchedulerState {
    tasks: Mutex<HashMap<String, JoinHandle<()>>>,
}

impl SchedulerState {
    pub fn new() -> Self {
        Self { tasks: Mutex::new(HashMap::new()) }
    }

    pub async fn start_task(
        &self,
        extension_id: String,
        command_id: String,
        interval_secs: u64,
        app: AppHandle,
    ) {
        let key = format!("{}::{}", extension_id, command_id);
        let handle = tokio::spawn(async move {
            let mut ticker = tokio::time::interval(
                std::time::Duration::from_secs(interval_secs)
            );
            ticker.tick().await; // skip first tick — worker may not be ready

            loop {
                ticker.tick().await;
                let msg = PendingMessage {
                    kind: MessageKind::Command,
                    command_id: command_id.clone(),
                };
                let mgr = app.state::<ExtensionManager>();
                match mgr.enqueue_worker(&extension_id, msg).await {
                    DispatchOutcome::ReadyDeliverNow { .. } => {
                        app.emit_all(EVENT_DELIVER, &DeliverPayload {
                            extension_id: extension_id.clone(),
                            command_id: command_id.clone(),
                        }).ok();
                    }
                    DispatchOutcome::NeedsMount => {
                        app.emit_all(EVENT_MOUNT, &MountPayload {
                            extension_id: extension_id.clone(),
                        }).ok();
                    }
                    DispatchOutcome::Degraded | DispatchOutcome::MountingWaitForReady => {
                        // transient — next tick will retry
                    }
                }
            }
        });

        self.tasks.lock().await.insert(key, handle);
    }

    pub async fn stop_task(&self, extension_id: &str, command_id: &str) {
        let key = format!("{}::{}", extension_id, command_id);
        if let Some(handle) = self.tasks.lock().await.remove(&key) {
            handle.abort();
        }
    }
}
```

### Interval validation
```rust
const MIN_INTERVAL_SECS: u64 = 10;
const MAX_INTERVAL_SECS: u64 = 86_400; // 24 hours

fn validate_interval(secs: u64) -> Result<(), Error> {
    if secs < MIN_INTERVAL_SECS || secs > MAX_INTERVAL_SECS {
        return Err(Error::InvalidInterval(secs));
    }
    Ok(())
}
```

### Extension manifest (declares schedule)
```json
{
  "id": "com.example.stocks",
  "commands": [
    {
      "id": "refresh",
      "name": "Refresh Prices",
      "schedule": { "interval": 60 }
    }
  ],
  "background": {
    "main": "worker.html"
  }
}
```

### Startup: spawn all scheduled tasks
```rust
pub async fn start_all_tasks(
    scheduler: &SchedulerState,
    extensions: &[ExtensionRecord],
    app: &AppHandle,
) {
    for ext in extensions.iter().filter(|e| e.enabled) {
        for cmd in &ext.manifest.commands {
            if let Some(schedule) = &cmd.schedule {
                if validate_interval(schedule.interval).is_ok() {
                    scheduler.start_task(
                        ext.id.clone(),
                        cmd.id.clone(),
                        schedule.interval,
                        app.clone(),
                    ).await;
                }
            }
        }
    }
}
```

### TypeScript: handle MOUNT event
```typescript
// Frontend listens for mount requests from the scheduler
listen('extensions:mount_worker', ({ payload }: { payload: { extensionId: string } }) => {
  extensionRuntime.mountWorker(payload.extensionId);
});
```

## Data contracts

**Manifest schedule field**:
```typescript
{
  interval: number; // seconds, 10–86400
}
```

**DeliverPayload** (Rust → TS event):
```typescript
{
  extensionId: string;
  commandId: string;
}
```

**MountPayload** (Rust → TS event):
```typescript
{
  extensionId: string;
}
```

## Dependencies & assumptions

- **Tokio** async runtime (included with Tauri v2)
- **`tauri::AppHandle`** passed into each spawned task for `emit_all`
- Extension runtime must expose `enqueue_worker(extId, msg)` → `DispatchOutcome` (or equivalent async message queue)
- Extension worker iframes must handle a `command` message type and respond accordingly

## To port this, you need:

- [ ] Tokio (or equivalent) async runtime with interval timers
- [ ] A `HashMap<String, JoinHandle>` (or equivalent cancellable handle store)
- [ ] Manifest schema: `commands[].schedule.interval` field
- [ ] Interval validation (min/max bounds enforcement)
- [ ] Skip-first-tick pattern (`ticker.tick().await` before the loop)
- [ ] Tauri event emission for DELIVER vs MOUNT outcomes
- [ ] Frontend handler for MOUNT events that creates the worker iframe

## Gotchas

- **Skip-first-tick is critical**: If you don't skip, the command fires at t=0 before the extension worker iframe has mounted. The extension receives a command it can't handle yet.
- **No catch-up**: Tasks are ephemeral. If the app was closed for 2 hours, a 60-second interval task doesn't run 120 times on restart — it just starts fresh. Design extensions accordingly (poll don't assume).
- **Abort vs cancel**: Tokio `JoinHandle::abort()` terminates the task without cleanup. If your scheduled task holds resources (DB connections, file handles), consider a CancellationToken instead so the task can clean up gracefully.
- **Multiple instances**: If `start_all_tasks` is called twice (e.g. during a hot reload), the old JoinHandle for a key is overwritten without abort, leaking a running task. Always call `stop_task` before re-starting.
- **Clock drift**: `tokio::time::interval` can drift under system load. If exact timing matters (e.g. "run at :00 of every minute"), use wall-clock alignment logic instead of simple interval timers.

## Origin (reference only)

Repo: https://github.com/Xoshbin/asyar  
Key file: `asyar-launcher/src-tauri/src/extensions/scheduler.rs`
