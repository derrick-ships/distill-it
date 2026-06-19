# Semantic Symbol Tools — from [Serena](https://github.com/oraios/serena)

> Domain: [[_domain]] · Source: https://github.com/oraios/serena · NotebookLM: <add link after upload>

## What it does

When an AI coding agent needs to work with code, the naive approach is to grep for text or read entire files. Serena's semantic symbol tools do something fundamentally different: they let an agent say "find the class `PaymentService`, replace the body of its `charge` method with this new implementation, then check if there are any type errors" — all without knowing line numbers, and without accidentally clobbering the wrong code block.

The tools expose symbol-level operations through an MCP server: find symbols by name or pattern, navigate hierarchies (class → method → inner function), see all references to a symbol, get the language server's diagnostics for it, replace its body, insert code before/after it, rename it across the whole codebase, or safely delete it if nothing else uses it.

## Why it exists

AI coding agents using only text-based tools (grep, sed, file reads) have a fundamental fragility problem: they work with line numbers and text patterns that break the moment the file changes. A refactor that moves a method three lines down silently shifts every line reference. Large files force agents to read thousands of lines just to find one method body.

The deeper issue is that LLMs produce better code edits when they operate at the semantic level — "replace this function" — rather than the syntactic level — "replace lines 47–83." Serena's team found that symbol-based operations reduce multi-step refactoring from "8–12 careful, error-prone steps" to clean atomic operations. The LSP backend provides this understanding for 40+ languages from a single API.

## How it actually works

**The LSP foundation.** Serena embeds a modified version of Microsoft's `multilspy` (called `solidlsp`) — a synchronous wrapper around Language Server Protocol servers. When you point it at a project, it starts one LSP process per configured language (e.g., Pyright for Python, rust-analyzer for Rust). The LSP server reads and indexes the whole project. From then on, Serena can ask it precise questions: "what symbols are in this file?", "who references this symbol?", "rename this symbol everywhere."

**The symbol data model.** Every piece of code is represented as a `LanguageServerSymbol`. It carries:
- `relative_path`, `line`, `column` — where the symbol name appears
- `body_start_position`, `body_end_position` — the full range of its definition
- `symbol_kind` — LSP SymbolKind (Function, Method, Class, Variable, etc.)
- `name` and `name_path` — the qualified hierarchy path, e.g. `PaymentService/charge`
- `children` — nested symbols, forming a tree

**Name paths as stable addresses.** Instead of line numbers, Serena uses name paths like `ClassName/method_name` or `/module/ClassName/method_name` as the address of any symbol. An agent can say "find `PaymentService/charge`" and it works regardless of where in the file that method lives. Overloaded methods (Java) get indexed like `method_name[0]`, `method_name[1]`.

**Reading operations.** The agent has a toolkit of read-only tools:
- `get_symbols_overview` — returns the top-level symbol tree for a file, grouped by kind (classes, functions, etc.), optionally with configurable depth
- `find_symbol` — searches the whole project (or a specific file) for symbols matching a name path pattern; supports substring matching, kind filtering, and optional inclusion of body text
- `find_referencing_symbols` — returns every symbol that *uses* the target, with code snippets showing where the reference appears
- `find_implementations` — finds concrete implementations of an interface or abstract method
- `find_declaration` — given a regex with one capture group, finds the symbol declaration in a file
- `get_diagnostics_for_file` / `get_diagnostics_for_symbol` — pulls the LSP's type errors and warnings, grouped by severity (1=Error, 2=Warning, 3=Info, 4=Hint)

**Editing operations.** Three structural edits work on symbols:
- `replace_symbol_body` — overwrites everything between a symbol's `body_start` and `body_end` with new content. The agent must have retrieved the symbol with `include_body=True` first, so it knows what it's replacing.
- `insert_after_symbol` / `insert_before_symbol` — inserts code at the line immediately after/before the symbol's body, handling newline conventions (some languages want a blank line between method definitions, some don't).
- `rename_symbol` — asks the LSP to produce a workspace edit that renames the symbol everywhere (across all files), then applies it. This is safe rename — the LSP knows about shadowing, string literals (opt-in), and comments (opt-in).
- `safe_delete_symbol` — checks whether the symbol has any references first; only deletes if there are none. If there are references, it returns their locations instead.

**Under the hood: edits are file operations.** When `replace_symbol_body` runs, the `LanguageServerCodeEditor` class does this: (1) look up the symbol's start/end positions, (2) send a `textDocument/didChange` notification to the LSP to delete the text between those positions, (3) send another `textDocument/didChange` to insert the new content at the start position. The LSP keeps its model in sync after every change. For rename, it asks the LSP for a `WorkspaceEdit` (a map of file → list of text edits and rename operations), then applies each edit.

**Result truncation.** All tools accept a `max_answer_chars` parameter. Large codebases return huge symbol trees; without truncation they'd blow past an LLM's context window. The tools apply progressive truncation: first drop body text, then limit children depth, then truncate the JSON string itself.

## The non-obvious parts

**Synchronous LSP communication is the hard engineering.** Standard LSP clients are async (they're designed for IDEs). Serena's `solidlsp` makes them synchronous by blocking on responses with `threading.Condition` variables. Diagnostics are especially tricky: the server *pushes* diagnostics via notifications (`textDocument/publishDiagnostics`) at unpredictable times, so `solidlsp` maintains a concurrent cache and waits with a configurable timeout for "fresh" diagnostics after an edit.

**Diagnostic timing after edits.** After a `replace_symbol_body` call, the agent almost certainly wants to see diagnostics. But diagnostics arrive asynchronously from the LSP. Serena's editing tools return a "diagnostic context result" — they wait a bit and surface any diagnostics already in the cache, making the edit-then-check loop natural.

**File buffer management.** The LSP server tracks which files are "open" via `textDocument/didOpen` / `textDocument/didClose` notifications. `solidlsp` maintains a reference-counted `LSPFileBuffer` layer: open a file context, do edits (which fire `didChange` notifications), close it. If you forget to close, the LSP's model of the file diverges from disk. This is handled via Python context managers.

**Cross-file references need a warmup delay.** Some LSP servers need a few seconds after indexing before their cross-file reference data is reliable. `solidlsp` includes a `_wait_for_cross_file_references_if_needed()` guard — a one-time startup delay on the first cross-file query. Without this, `find_referencing_symbols` can return empty results even when references clearly exist.

**Two backends, same interface.** There's a JetBrains plugin backend alongside the LSP backend. For agents in a JetBrains IDE, they delegate to the IDE's own analysis instead of running a separate LSP server. The symbol interface (`LanguageServerSymbol` / `JetBrainsSymbol`) is shared so tools work identically regardless of backend.

**Tool output is structured for LLMs.** All results are JSON. Symbol output includes `to_dict()` serialization with configurable depth and field inclusion — the agent can ask for just names (to orient itself cheaply) or full bodies (to read and edit). The `LanguageServerSymbolDictGrouper` collapses single-child groups for readability.

## Related
- [[agent-dashboard--from-serena]] (the monitoring dashboard that shows tool calls and diagnostics live)
- [[language-server-manager--from-serena]] (the concurrent LSP startup/management layer that backs these tools)
- See also: Tree-sitter for syntax-level (not semantic) parsing without a language server; Jedi for Python-only symbol analysis
