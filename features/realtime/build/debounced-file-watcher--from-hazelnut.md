# Debounced File Watcher (build spec) — distilled from hazelnut

## Summary

Watch directories via the OS notification API (`notify`), push events to a channel, poll non-blockingly,
**debounce** by last-seen-time per path, act only on Create/Modify, route each file to its watched
directory's allowed rule set via **longest-prefix canonical matching**, and run a **background initial
scan** of existing files on watch start. Skip symlinks and NotFound races; track a shared atomic
processed-count.

## Core logic (inlined)

### Watcher (Rust, `watcher/mod.rs`)

```rust
pub struct Watcher {
    watcher: RecommendedWatcher,                 // notify crate
    engine: RuleEngine,
    rx: mpsc::Receiver<Result<notify::Event, notify::Error>>,
    event_handler: EventHandler,                 // the debouncer
    files_processed: Arc<AtomicU64>,
    watch_rules: HashMap<PathBuf, Vec<String>>,  // canonical dir -> allowed rule names ([] = all)
    canonical_cache: HashMap<PathBuf, PathBuf>,
}

impl Watcher {
    pub fn new(engine, polling_interval_secs, debounce_seconds) -> Result<Self> {
        let (tx, rx) = mpsc::channel();
        let watcher = RecommendedWatcher::new(
            move |res| { let _ = tx.send(res); },           // callback pushes events to channel
            Config::default().with_poll_interval(Duration::from_secs(polling_interval_secs)))?;
        Ok(Self { watcher, engine, rx, event_handler: EventHandler::new(debounce_seconds), ... })
    }

    pub fn watch_with_rules(&mut self, path, recursive, rules: Vec<String>) -> Result<()> {
        let mode = if recursive { RecursiveMode::Recursive } else { RecursiveMode::NonRecursive };
        self.watcher.watch(path, mode)?;
        let canonical = fs::canonicalize(path).unwrap_or(path.to_path_buf());
        self.watch_rules.insert(canonical.clone(), rules);
        // background initial scan so existing files get processed without blocking the UI:
        std::thread::spawn(move || scan_existing_background(&scan_path, recursive, &rules_snapshot, allowed, counter));
        Ok(())
    }

    pub fn poll(&self) -> Result<Vec<notify::Event>> {           // non-blocking drain
        let mut events = Vec::new();
        while let Ok(Ok(event)) = self.rx.try_recv() { events.push(event); }
        Ok(events)
    }

    pub fn process_polled_events(&mut self, events) -> Result<usize> {
        let mut processed = 0;
        for event in events {
            match event.kind {
                EventKind::Create(_) | EventKind::Modify(_) => {        // ONLY these
                    for path in self.event_handler.should_process(&event) {   // debounce
                        let allowed = self.allowed_rules_for(&path);           // longest-prefix match
                        match self.engine.process_filtered(&path, allowed) {
                            Ok(true) => processed += 1,
                            Ok(false) => {}
                            Err(e) if is_not_found(&e) => continue,            // file vanished — skip
                            Err(e) => { /* notify_rule_error */ }
                        }
                    }
                }
                _ => {}                                                  // ignore delete/rename-away
            }
        }
        self.event_handler.cleanup();
        self.files_processed.fetch_add(processed as u64, Ordering::Relaxed);
        Ok(processed)
    }
}
```

### Debounce handler (`watcher/handler.rs`)

```rust
pub struct EventHandler { recent: IndexMap<PathBuf, Instant>, debounce: Duration }
impl EventHandler {
    pub fn new(debounce_seconds: u64) -> Self { Self { recent: IndexMap::new(), debounce: Duration::from_secs(debounce_seconds) } }
    pub fn should_process(&mut self, event: &Event) -> Vec<PathBuf> {
        let now = Instant::now();
        event.paths.iter().filter(|p| {
            let pass = self.recent.get(*p).map(|&last| now.duration_since(last) > self.debounce).unwrap_or(true);
            self.recent.insert((*p).clone(), now);   // always record last-seen
            pass
        }).cloned().collect()
    }
    pub fn cleanup(&mut self) {                       // drop entries older than 10x window
        let now = Instant::now(); let threshold = self.debounce * 10;
        self.recent.retain(|_, &mut t| now.duration_since(t) < threshold);
    }
}
```

### Longest-prefix routing + background scan

```rust
fn allowed_rules_for(&self, file_path) -> Option<&[String]> {
    // pick the watched dir that is a prefix of file_path with the LONGEST canonical path (most specific)
    // try raw path first (no syscall); fall back to fs::canonicalize only if nothing matched (symlinks)
}
fn scan_existing_background(path, recursive, rules, allowed, counter) {
    let engine = RuleEngine::new(rules.to_vec());
    let entries = if recursive { walkdir(path)? } else { fs::read_dir(path)? };  // walkdir skips symlinks
    for entry in entries { let _ = engine.process_filtered(&entry.path(), allowed); }   // count matches
}
```

## Data contracts

- **Watcher::new(engine, polling_interval_secs, debounce_seconds)**.
- **watch_with_rules(path, recursive: bool, allowed_rule_names: Vec<String>)** (`[]` = all rules).
- **Event** (from `notify`): `{ kind: Create|Modify|..., paths: Vec<PathBuf> }`.
- **poll() -> Vec<Event>**; **process_polled_events(events) -> processed_count**.

## Dependencies & assumptions

- Rust: `notify` (cross-platform FS events), `indexmap`, `std::sync::mpsc`, atomics, threads. The rule
  engine ([[file-rules-engine--from-hazelnut]]).
- Swappable: any OS file-notification lib; the debounce + initial-scan + prefix-routing patterns are language-agnostic.

## To port this, you need:

- [ ] An OS file-watch lib feeding events into a channel; a non-blocking poll/drain.
- [ ] A **last-seen-time debounce** map + periodic cleanup (drop entries > N× window).
- [ ] Act only on create/modify; ignore deletes/renames-away.
- [ ] An **initial scan** of existing files on watch-start, on a background thread.
- [ ] Per-directory rule routing via longest-prefix (canonical) path matching, raw-path-first.
- [ ] Skip symlinks; treat NotFound (file vanished) as a skip, not an error.

## Gotchas

- **Debounce or you act on half-written files** — downloads fire many modify events; act once after quiet.
- **Last-seen debounce, not a fixed delay** — collapses bursts without adding latency to isolated events.
- **Scan on start, off-thread** — otherwise you miss pre-existing files or block UI startup.
- **NotFound is normal** — files disappear between event and processing; skip, don't error.
- **Canonicalize for routing, but raw-path-first** — canonicalizing every event is a syscall per event; only fall back for symlinks.
- **Bound the debounce map** — a busy folder grows it without the 10× cleanup.

## Origin (reference only)

ricardodantas/hazelnut @ `main`: `src/watcher/mod.rs` (Watcher — inlined), `src/watcher/handler.rs`
(debounce — inlined), `src/rules/engine.rs` (`process_filtered`).

**Gaps to verify (cost-capped):** exact `notify` config/backends per OS; how the daemon loop drives `process_events`; `walkdir` symlink/error handling specifics.
