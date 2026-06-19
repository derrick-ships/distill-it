# File Actions Executor — from [hazelnut](https://github.com/ricardodantas/hazelnut)

> Domain: [[_domain]] · Source: https://github.com/ricardodantas/hazelnut · NotebookLM: <link once added>

## What it does

This is the "then do this" half of the rules. When a rule matches a file, an **action** runs: move it,
copy it, rename it (with a pattern), send it to the trash, delete it, zip it into an archive, or run a
custom shell command/script against it. Move/copy can auto-create the destination folder and choose
whether to overwrite; rename and run-command support placeholders like `{name}`, `{ext}`, `{date}`,
`{path}`, `{dir}` so you can build dynamic names and command lines.

## Why it exists

Watching and matching are useless without *doing*. The action set is exactly the vocabulary of file
chores people automate with Hazel: tidy downloads into folders, archive old files, trash junk, or hand
a file to a custom script (compress an image, upload, notify). Making "run a script" a first-class
action is what turns a file organizer into a general automation tool — anything you can express as a
command becomes a rule.

## How it actually works

`Action` is a tagged enum: `Move { destination, create_destination, overwrite }`, `Copy { … }`,
`Rename { pattern }`, `Trash`, `Delete`, `RunScript/RunCommand { command, args }`, and `Archive {
destination }`. Each variant has an `execute(path)` implementation:

- **Move / Copy**: expand the destination path (handling `~` for home), create the folder if
  `create_destination` is set, and refuse to clobber an existing file unless `overwrite` is true.
- **Trash**: hand the file to the OS trash (via the `trash` crate) rather than hard-deleting — recoverable.
- **Delete**: permanent removal.
- **Rename**: build a new filename from a pattern with placeholders substituted (`{name}` = stem,
  `{ext}` = extension, `{date}` = today, etc.).
- **Archive**: zip the file into a `.zip` (named after the file) at an optional destination.
- **RunScript**: substitute placeholders (`{path}`, `{name}`, `{dir}`) into the command + args and spawn
  it through the platform shell (`cmd` on Windows, `sh -c` elsewhere), so the matched file is passed to
  arbitrary tooling.

The engine that calls these knows which actions are **destructive** (move/rename/trash/delete) and stops
running further actions on a file once one of those fires — because the source path is gone.

## The non-obvious parts

- **Trash ≠ Delete, on purpose.** Sending to the OS trash is the safe default verb; permanent delete is
  a separate, deliberate action. For an automated tool touching your files unattended, recoverability
  matters.
- **Overwrite is opt-in.** Move/copy refuse to overwrite an existing destination unless you explicitly
  allow it — automation shouldn't silently destroy data.
- **`create_destination` is a flag, not a guess** — the folder is made only if you asked, so a typo'd
  path fails loudly instead of spawning stray directories.
- **Placeholders are the power feature.** `{name}/{ext}/{date}` in rename and `{path}/{name}/{dir}` in
  run-command turn static actions into templates — this is what makes "run a script per file" useful.
- **Shell-per-OS.** Custom commands run through `cmd`/`sh -c`, so you write normal shell, and the file's
  path is injected as a placeholder.
- **Path expansion handles `~`** so destinations can be written relative to home.

## Related
- [[file-rules-engine--from-hazelnut]] (decides when these run; stops after a destructive action)
- [[debounced-file-watcher--from-hazelnut]] (the source of files to act on)
- See also: [[pipeline-orchestration]] peers; "run a custom script" overlaps with action/automation tooling.
