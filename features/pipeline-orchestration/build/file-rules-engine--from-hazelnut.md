# File Rules Engine (build spec) — distilled from hazelnut

## Summary

Condition→action rules over file paths. A `Condition` is an all-optional struct matched by **AND**
(every set criterion must hold; empty = matches all); criteria: extension(s), glob name, regex name,
size >/<, age-days >/<, is_directory, is_hidden. The `RuleEngine` evaluates ordered, enable-able rules
(`evaluate_first`/`all`/`filtered`-by-name) and executes matched actions, **stopping after a destructive
action**. Perf: one `metadata()` syscall for all size/age checks; thread-local cap-1000 caches for
compiled glob/regex.

## Core logic (inlined)

### Rule + Condition (`rules/mod.rs`, `rules/condition.rs`)

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rule { pub name: String, pub enabled: bool, pub condition: Condition, pub action: Action, pub stop_processing: bool }

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Condition {              // ALL optional; matched by AND over set fields
    #[serde(default)] pub extension: Option<String>,           // single ext, no dot, case-insensitive
    #[serde(default)] pub extensions: Vec<String>,             // any-of
    #[serde(default)] pub name_matches: Option<String>,        // glob over FILE NAME
    #[serde(default)] pub name_regex: Option<String>,          // regex over file name
    #[serde(default)] pub size_greater_than: Option<u64>,      // bytes
    #[serde(default)] pub size_less_than: Option<u64>,
    #[serde(default)] pub age_days_greater_than: Option<u64>,  // days since mtime
    #[serde(default)] pub age_days_less_than: Option<u64>,
    #[serde(default)] pub is_directory: Option<bool>,
    #[serde(default)] pub is_hidden: Option<bool>,             // name starts with '.'
}

impl Condition {
    pub fn matches(&self, path: &Path) -> Result<bool> {
        if let Some(ext) = &self.extension { if !check_extension(path, ext) { return Ok(false); } }
        if !self.extensions.is_empty() && !self.extensions.iter().any(|e| check_extension(path, e)) { return Ok(false); }
        if let Some(p) = &self.name_matches { if !check_glob(path, p)? { return Ok(false); } }
        if let Some(p) = &self.name_regex   { if !check_regex(path, p)? { return Ok(false); } }
        if self.size_greater_than.is_some() || self.size_less_than.is_some()
           || self.age_days_greater_than.is_some() || self.age_days_less_than.is_some() {
            let md = match path.metadata() { Ok(m) => m, Err(_) => return Ok(false) };   // ONE syscall
            if let Some(min) = self.size_greater_than { if md.len() <= min { return Ok(false); } }
            if let Some(max) = self.size_less_than    { if md.len() >= max { return Ok(false); } }
            if self.age_days_greater_than.is_some() || self.age_days_less_than.is_some() {
                let age = md.modified()?.elapsed().map(|d| d.as_secs()/86400).unwrap_or(0);
                if let Some(d) = self.age_days_greater_than { if age <= d { return Ok(false); } }
                if let Some(d) = self.age_days_less_than    { if age >= d { return Ok(false); } }
            }
        }
        if let Some(want) = self.is_directory { if path.is_dir() != want { return Ok(false); } }
        if let Some(want) = self.is_hidden {
            let hidden = path.file_name().and_then(|n| n.to_str()).unwrap_or("").starts_with('.');
            if hidden != want { return Ok(false); }
        }
        Ok(true)   // nothing contradicted
    }
}

fn check_extension(path, ext) -> bool { path.extension().and_then(|e| e.to_str()).map(|e| e.eq_ignore_ascii_case(ext)).unwrap_or(false) }
```

### Compiled-pattern caches (thread-local, cap-and-clear)

```rust
const CACHE_MAX_ENTRIES: usize = 1000;
thread_local! {
    static GLOB_CACHE:  RefCell<HashMap<String, glob::Pattern>> = RefCell::new(HashMap::new());
    static REGEX_CACHE: RefCell<HashMap<String, Regex>>         = RefCell::new(HashMap::new());
}
fn check_glob(path, pattern) -> Result<bool> {
    let name = path.file_name()...;
    GLOB_CACHE.with(|c| { let mut c = c.borrow_mut();
        if c.len() >= CACHE_MAX_ENTRIES && !c.contains_key(pattern) { c.clear(); }   // cap: clear wholesale
        let pat = c.entry(pattern.into()).or_insert_with(|| glob::Pattern::new(pattern).unwrap()).clone();
        Ok(pat.matches(name)) })
}
// check_regex is identical with Regex::new.
```

### Engine (`rules/engine.rs`)

```rust
pub struct RuleEngine { rules: Vec<Rule> }
impl RuleEngine {
    pub fn evaluate_first(&self, path) -> Result<Option<Action>> {          // first enabled match
        for r in &self.rules { if r.enabled && r.condition.matches(path)? { return Ok(Some(r.action.clone())); } }
        Ok(None)
    }
    pub fn evaluate_all(&self, path) -> Result<Vec<Action>> {               // all matches; honor stop_processing
        let mut out = vec![];
        for r in &self.rules { if r.enabled && r.condition.matches(path)? { out.push(r.action.clone()); if r.stop_processing { break; } } }
        Ok(out)
    }
    pub fn evaluate_filtered(&self, path, allowed: Option<&[String]>) -> Result<Vec<Action>> {
        match allowed { Some(names) if !names.is_empty() =>
            /* like evaluate_all but skip rules whose name isn't in `names` */, _ => self.evaluate_all(path) }
    }
    pub fn process_filtered(&self, path, allowed) -> Result<bool> {
        let actions = self.evaluate_filtered(path, allowed)?;
        if actions.is_empty() { return Ok(false); }
        for a in &actions {
            a.execute(path)?;
            if matches!(a, Action::Move{..}|Action::Rename{..}|Action::Trash|Action::Delete) { break; }  // source gone
        }
        Ok(true)
    }
}
```

## Data contracts

- **Rule:** `{name:str, enabled:bool, condition:Condition, action:Action, stop_processing:bool}` (serde — lives in config).
- **Condition:** the all-optional struct above (AND semantics; empty matches all).
- **Engine API:** `evaluate_first|evaluate_all|evaluate_filtered(path, allowed_names?) -> actions`; `process_filtered -> bool` (executed).

## Dependencies & assumptions

- Rust: `serde`, `glob`, `regex`, `anyhow`. The action executor ([[file-actions-executor--from-hazelnut]]).
- Glob/regex match the **file name**, not the full path. Swappable: the optional-struct-AND pattern is language-agnostic.

## To port this, you need:

- [ ] A serializable `Rule {name, enabled, condition, action, stop_processing}`.
- [ ] An all-optional `Condition` struct matched by AND (short-circuit on first miss; empty = all).
- [ ] One lazy metadata fetch shared by all size/age checks.
- [ ] A compiled-pattern cache (cap + clear) for glob/regex.
- [ ] Ordered evaluation with `evaluate_first/all/filtered`; `stop_processing`; name-based filtering.
- [ ] Execute matched actions, **stopping after a destructive one** (move/rename/trash/delete).

## Gotchas

- **AND over set fields, ignore unset** — an empty condition must match everything, or "catch-all" rules break.
- **Fetch metadata once** — calling `path.metadata()` per size/age check triples the syscalls on the hot path.
- **Cap the pattern cache** — a rule generating dynamic patterns would otherwise leak memory; clear-wholesale at the cap is the simple fix.
- **Stop after destructive actions** — running a second action on a moved/deleted file errors (or worse, hits the wrong file).
- **Match the name, not the path** — globbing the full path surprises users organizing by filename.
- **Case-insensitive extensions** — `.PDF` must match `pdf`.

## Origin (reference only)

ricardodantas/hazelnut @ `main`: `src/rules/condition.rs` (Condition.matches + caches — inlined),
`src/rules/engine.rs` (RuleEngine — inlined), `src/rules/mod.rs` (Rule struct).

**Gaps to verify (cost-capped):** config (de)serialization shape (`src/config/schema.rs`); whether glob is case-sensitive; exact age rounding at day boundaries.
