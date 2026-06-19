# File Actions Executor (build spec) — distilled from hazelnut

## Summary

A tagged `Action` enum with per-variant `execute(path)`: **Move/Copy** (`~`-expanded destination,
optional `create_destination`, overwrite-guarded), **Rename** (pattern with `{name}/{ext}/{date}`),
**Trash** (OS trash, recoverable), **Delete** (permanent), **Archive** (zip), **RunScript** (placeholder
substitution `{path}/{name}/{dir}` → spawned via the platform shell). The caller treats
move/rename/trash/delete as destructive and stops the action chain after them.

## Core logic (inlined)

### Action enum + execute (`rules/action.rs`)

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Action {
    Move   { destination: PathBuf, create_destination: bool, overwrite: bool },
    Copy   { destination: PathBuf, create_destination: bool, overwrite: bool },
    Rename { pattern: String },          // supports {name}, {ext}, {date}, ...
    Trash,
    Delete,
    RunScript { command: String, args: Vec<String> },   // args support {path}, {name}, {dir}, ...
    Archive { destination: Option<PathBuf> },            // zip
}

impl Action {
    pub fn execute(&self, path: &Path) -> Result<()> {
        match self {
            Action::Move { destination, create_destination, overwrite } => {
                let dest = expand_path(destination);                 // handle ~
                if *create_destination { fs::create_dir_all(&dest)?; }
                let dest_path = dest.join(path.file_name().unwrap());
                if dest_path.exists() && !overwrite {
                    bail!("Destination exists and overwrite is false: {}", dest_path.display());
                }
                fs::rename(path, &dest_path)                          // (falls back to copy+remove across filesystems)
                    .or_else(|_| { fs::copy(path, &dest_path)?; fs::remove_file(path) })?;
            }
            Action::Copy { destination, create_destination, overwrite } => {
                let dest = expand_path(destination);
                if *create_destination { fs::create_dir_all(&dest)?; }
                let dest_path = dest.join(path.file_name().unwrap());
                if dest_path.exists() && !overwrite { bail!("...overwrite is false..."); }
                fs::copy(path, &dest_path)?;
            }
            Action::Trash  => { trash::delete(path)?; }              // OS trash — recoverable
            Action::Delete => { fs::remove_file(path)?; }            // permanent
            Action::Rename { pattern } => {
                let new_name = expand_placeholders(pattern, path);   // {name}{ext}{date}
                fs::rename(path, path.with_file_name(new_name))?;
            }
            Action::Archive { destination } => {
                let archive_path = destination.clone().unwrap_or_else(|| path.parent().unwrap().to_path_buf())
                    .join(format!("{}.zip", path.file_name().unwrap().to_string_lossy()));
                let zip = ZipWriter::new(fs::File::create(&archive_path)?);
                /* add `path` to the zip, finish */
            }
            Action::RunScript { command, args } => {
                let actual = expand_placeholders(command, path);     // {path}{name}{dir}
                let argv: Vec<String> = args.iter().map(|a| expand_placeholders(a, path)).collect();
                let shell     = if cfg!(windows) { "cmd" } else { "sh" };
                let shell_arg = if cfg!(windows) { "/C"  } else { "-c" };
                let mut child = Command::new(shell).arg(shell_arg).arg(format!("{actual} {}", argv.join(" "))).spawn()?;
                child.wait()?;
            }
        }
        Ok(())
    }
}
```

### Placeholder + path expansion

```rust
fn expand_placeholders(template: &str, path: &Path) -> String {
    let name = path.file_stem()...; let ext = path.extension()...; let dir = path.parent()...;
    template.replace("{name}", name).replace("{ext}", ext)
            .replace("{path}", &path.display().to_string()).replace("{dir}", dir)
            .replace("{date}", &today_yyyy_mm_dd())
}
fn expand_path(p: &Path) -> PathBuf { /* replace leading ~ with $HOME */ }
```

## Data contracts

- **Action** (serde-tagged enum) as above — lives in the rule config.
- **Move/Copy:** `{destination: PathBuf, create_destination: bool, overwrite: bool}`.
- **Rename:** `{pattern: String}` with `{name}|{ext}|{date}`.
- **RunScript:** `{command: String, args: Vec<String>}` with `{path}|{name}|{dir}`.
- **execute(path) -> Result<()>** — errors bubble (overwrite refusal, spawn failure, IO).
- **Destructive set (caller stops after):** Move, Rename, Trash, Delete.

## Dependencies & assumptions

- Rust: `std::fs`, `std::process::Command`, `trash` crate, a zip crate, `serde`, `anyhow`. The engine
  ([[file-rules-engine--from-hazelnut]]) calls `execute` and enforces the destructive-stop.
- Swappable: trash lib, zip lib, shell choice. Placeholder set is extensible.

## To port this, you need:

- [ ] A tagged action enum with per-variant `execute(path)`.
- [ ] `~`/home path expansion; opt-in `create_destination`; overwrite-guarded move/copy.
- [ ] Trash (recoverable) as distinct from permanent delete.
- [ ] Placeholder substitution (`{name}/{ext}/{date}/{path}/{dir}`) for rename + run-command.
- [ ] Run-command via the platform shell (`cmd /C` vs `sh -c`).
- [ ] A "destructive" classification so the caller stops the chain after the source is gone.

## Gotchas

- **Default to Trash, not Delete** — an unattended tool that hard-deletes is dangerous; make permanent delete explicit.
- **Never overwrite silently** — guard move/copy on an `overwrite` flag or automation eats data.
- **Cross-filesystem move** — `fs::rename` fails across mounts; fall back to copy+remove.
- **Quote/escape placeholders in shell commands** — naive `{path}` interpolation breaks on spaces; the safest port passes args as argv, not a joined string.
- **`create_destination` opt-in** — auto-creating on every move scatters folders from typos.
- **Stop after destructive actions** — the engine must not run a second action on a moved/trashed file.

## Origin (reference only)

ricardodantas/hazelnut @ `main`: `src/rules/action.rs` (Action enum + execute — inlined/grepped),
`src/rules/engine.rs` (destructive-stop logic).

**Gaps to verify (cost-capped):** exact placeholder set + date format; archive (zip) details; shell
argument quoting/escaping; cross-filesystem move fallback (inferred, confirm); full RunScript stdout/stderr handling.
