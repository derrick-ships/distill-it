# Semantic Symbol Tools (build spec) — distilled from Serena

## Summary
Build a set of MCP-exposed tools that give an AI agent symbol-level read and edit operations over a codebase, backed by Language Server Protocol. Instead of grep/line-number edits, the agent uses stable name-path addresses (`ClassName/method_name`) to find, navigate, replace, insert, rename, and delete code symbols — with the LSP keeping the semantic model in sync after every change.

## Core logic (inlined)

### Symbol data model
```python
@dataclass
class SymbolLocation:
    relative_path: str
    line: int           # 0-based, position of symbol identifier
    column: int         # 0-based

@dataclass
class Position:
    line: int           # 0-based
    character: int      # 0-based

@dataclass
class Symbol:
    name: str
    name_path: str          # e.g. "PaymentService/charge"
    kind: SymbolKind        # LSP SymbolKind enum
    location: SymbolLocation
    body_start: Position
    body_end: Position
    body: str | None        # populated only if requested
    children: dict[str, list["Symbol"]]  # by kind
    overload_idx: int | None   # for Java overloads

def to_dict(symbol, depth=2, include_body=False) -> dict:
    d = {
        "name": symbol.name,
        "name_path": symbol.name_path,
        "kind": symbol.kind.name,
        "location": {"path": symbol.location.relative_path,
                     "line": symbol.location.line},
    }
    if include_body:
        d["body"] = symbol.body
        d["body_location"] = {
            "start": {"line": symbol.body_start.line, "col": symbol.body_start.character},
            "end":   {"line": symbol.body_end.line,   "col": symbol.body_end.character},
        }
    if depth > 0:
        d["children"] = {
            kind: [to_dict(c, depth-1, include_body) for c in children]
            for kind, children in symbol.children.items()
        }
    return d
```

### Name path matching
```python
class NamePathMatcher:
    """Three matching modes:
       - simple:   "charge"           → matches any symbol named "charge"
       - relative: "Service/charge"   → matches "charge" inside any "Service"
       - absolute: "/module/Service/charge" → exact full path match
    Optionally substring: pattern anywhere in name.
    Overload: "charge[1]" targets second overload.
    """
    def matches(self, symbol: Symbol) -> bool:
        if self.is_absolute:
            return symbol.name_path == self.pattern.lstrip("/")
        parts = self.pattern.split("/")
        sym_parts = symbol.name_path.split("/")
        if self.is_relative:
            # check if pattern is a suffix of the name path
            return sym_parts[-len(parts):] == parts
        # simple: just the last part
        target_name = parts[-1]
        if self.substring:
            return target_name in symbol.name
        return symbol.name == target_name
```

### LSP communication wrapper (synchronous)
```python
class SolidLanguageServer:
    def __init__(self, project_root, lsp_process):
        self._process = lsp_process          # started LSP server subprocess
        self._file_buffers: dict[str, FileBuffer] = {}
        self._symbol_cache: dict[str, CachedSymbols] = {}
        self._diag_cache: dict[str, list[Diagnostic]] = {}
        self._diag_condition = threading.Condition()

    # ---- Document management ----
    def open_file(self, rel_path) -> ContextManager[FileBuffer]:
        # sends textDocument/didOpen, refcounts, sends didClose on exit
        ...

    def insert_text_at_position(self, rel_path, line, col, text):
        # sends textDocument/didChange with incremental insert
        buf = self._file_buffers[rel_path]
        buf.apply_insert(line, col, text)
        self._send_did_change(rel_path, buf.version, [
            {"range": {"start": {"line": line, "character": col},
                       "end":   {"line": line, "character": col}},
             "text": text}
        ])

    def delete_text_between(self, rel_path, start: Position, end: Position) -> str:
        # sends textDocument/didChange with range deletion
        ...

    # ---- Symbol queries ----
    def request_document_symbols(self, rel_path) -> list[Symbol]:
        content_hash = hash(self._file_buffers[rel_path].content)
        if cached := self._symbol_cache.get(rel_path):
            if cached.content_hash == content_hash:
                return cached.symbols
        raw = self._send_request("textDocument/documentSymbol",
                                 {"textDocument": {"uri": to_uri(rel_path)}})
        symbols = self._parse_symbols(raw)
        self._symbol_cache[rel_path] = CachedSymbols(content_hash, symbols)
        return symbols

    def request_references(self, rel_path, line, col) -> list[Location]:
        return self._send_request("textDocument/references", {
            "textDocument": {"uri": to_uri(rel_path)},
            "position": {"line": line, "character": col},
            "context": {"includeDeclaration": False}
        })

    def request_rename(self, rel_path, line, col, new_name) -> WorkspaceEdit:
        return self._send_request("textDocument/rename", {
            "textDocument": {"uri": to_uri(rel_path)},
            "position": {"line": line, "character": col},
            "newName": new_name
        })

    def request_diagnostics(self, rel_path, timeout=10.0) -> list[Diagnostic]:
        # Try pull diagnostics first
        try:
            return self._send_request("textDocument/diagnostic",
                                      {"textDocument": {"uri": to_uri(rel_path)}})
        except LSPMethodNotSupported:
            pass
        # Fall back to waiting for push notification
        with self._diag_condition:
            self._diag_condition.wait_for(
                lambda: rel_path in self._diag_cache, timeout=timeout
            )
        return self._diag_cache.get(rel_path, [])

    def _on_publish_diagnostics(self, params):
        rel_path = from_uri(params["uri"])
        with self._diag_condition:
            self._diag_cache[rel_path] = params["diagnostics"]
            self._diag_condition.notify_all()
```

### Symbol retriever (high-level facade)
```python
class SymbolRetriever:
    def __init__(self, ls_manager: LanguageServerManager, project_root: str):
        self.ls_manager = ls_manager
        self.project_root = project_root

    def find(self, name_path_pattern: str,
             in_file: str | None = None,
             include_body: bool = False,
             include_kinds: list[str] | None = None) -> list[Symbol]:
        matcher = NamePathMatcher(name_path_pattern)
        if in_file:
            ls = self.ls_manager.get_for_file(in_file)
            all_syms = self._flatten(ls.request_document_symbols(in_file))
        else:
            all_syms = self._all_project_symbols()
        results = [s for s in all_syms if matcher.matches(s)]
        if include_kinds:
            results = [s for s in results if s.kind.name in include_kinds]
        if include_body:
            for s in results:
                s.body = self._read_body(s)
        return results

    def find_referencing_symbols(self, symbol: Symbol) -> list[ReferenceInSymbol]:
        ls = self.ls_manager.get_for_file(symbol.location.relative_path)
        locs = ls.request_references(
            symbol.location.relative_path,
            symbol.location.line,
            symbol.location.column
        )
        result = []
        for loc in locs:
            ref_path = from_uri(loc["uri"])
            ref_syms = self._flatten(ls.request_document_symbols(ref_path))
            # find the containing symbol at loc position
            containing = self._find_containing_symbol(ref_syms, loc["range"]["start"])
            if containing:
                result.append(ReferenceInSymbol(
                    symbol=containing,
                    line=loc["range"]["start"]["line"],
                    column=loc["range"]["start"]["character"]
                ))
        return result

    def get_diagnostics(self, symbol: Symbol) -> list[Diagnostic]:
        ls = self.ls_manager.get_for_file(symbol.location.relative_path)
        all_diags = ls.request_diagnostics(symbol.location.relative_path)
        # filter to those within the symbol's body range
        return [d for d in all_diags
                if symbol.body_start.line <= d["range"]["start"]["line"]
                        <= symbol.body_end.line]
```

### Code editor (edit operations)
```python
class CodeEditor:
    def __init__(self, ls_manager, project_root):
        self.ls_manager = ls_manager
        self.project_root = project_root

    def replace_body(self, symbol: Symbol, new_body: str):
        assert symbol.body is not None, "retrieve with include_body=True first"
        ls = self.ls_manager.get_for_file(symbol.location.relative_path)
        with ls.open_file(symbol.location.relative_path) as buf:
            ls.delete_text_between(
                symbol.location.relative_path,
                symbol.body_start, symbol.body_end
            )
            ls.insert_text_at_position(
                symbol.location.relative_path,
                symbol.body_start.line, symbol.body_start.character,
                new_body.strip()
            )
            buf.flush_to_disk()   # write the in-memory buffer back to the file

    def insert_after(self, symbol: Symbol, content: str):
        ls = self.ls_manager.get_for_file(symbol.location.relative_path)
        with ls.open_file(symbol.location.relative_path) as buf:
            # insert at start of the line after body_end
            insert_line = symbol.body_end.line + 1
            ls.insert_text_at_position(
                symbol.location.relative_path,
                insert_line, 0,
                _normalize_leading_newlines(content, symbol.kind)
            )
            buf.flush_to_disk()

    def rename(self, symbol: Symbol, new_name: str) -> str:
        ls = self.ls_manager.get_for_file(symbol.location.relative_path)
        workspace_edit = ls.request_rename(
            symbol.location.relative_path,
            symbol.location.line, symbol.location.column,
            new_name
        )
        n_changes = self._apply_workspace_edit(workspace_edit)
        return f"Renamed to '{new_name}' in {n_changes} location(s)."

    def safe_delete(self, symbol: Symbol) -> str:
        retriever = SymbolRetriever(self.ls_manager, self.project_root)
        refs = retriever.find_referencing_symbols(symbol)
        if refs:
            return f"Cannot delete: {len(refs)} reference(s) found: " + \
                   ", ".join(f"{r.symbol.name_path}:{r.line}" for r in refs)
        # no references → delete the body text
        ls = self.ls_manager.get_for_file(symbol.location.relative_path)
        with ls.open_file(symbol.location.relative_path) as buf:
            ls.delete_text_between(
                symbol.location.relative_path,
                symbol.body_start, symbol.body_end
            )
            buf.flush_to_disk()
        return f"Deleted '{symbol.name_path}'."
```

### MCP tool wrappers
```python
# Each MCP tool is a thin wrapper delegating to SymbolRetriever + CodeEditor.
# Example — FindSymbolTool:
class FindSymbolTool(Tool, ToolMarkerSymbolicRead):
    def apply(
        self,
        name_path_pattern: str,
        relative_path: str | None = None,
        include_body: bool = False,
        include_kinds: list[str] | None = None,
        max_results: int = 20,
        max_answer_chars: int = 50_000,
    ) -> str:
        """Find symbols matching name_path_pattern in the project or a specific file."""
        results = self.retriever.find(
            name_path_pattern, in_file=relative_path,
            include_body=include_body, include_kinds=include_kinds
        )[:max_results]
        output = json.dumps([to_dict(s, depth=2, include_body=include_body) for s in results])
        return truncate_to(output, max_answer_chars)
```

## Data contracts

**Symbol dict (serialized output)**
```json
{
  "name": "charge",
  "name_path": "PaymentService/charge",
  "kind": "Method",
  "location": { "path": "services/payment.py", "line": 42 },
  "body_location": {
    "start": { "line": 42, "col": 4 },
    "end":   { "line": 61, "col": 0 }
  },
  "body": "def charge(self, amount: int) -> bool:\n    ...",
  "children": {
    "Variable": [ { "name": "result", "name_path": "PaymentService/charge/result", ... } ]
  }
}
```

**Diagnostic dict**
```json
{
  "message": "Argument of type 'str' cannot be assigned to parameter 'amount' of type 'int'",
  "severity": 1,
  "range": { "start": { "line": 55, "character": 16 }, "end": { "line": 55, "character": 22 } }
}
```

**WorkspaceEdit (applied by rename)**
```json
{
  "changes": {
    "file:///path/services/payment.py": [
      { "range": { "start": { "line": 42, "character": 8 }, "end": { "line": 42, "character": 14 } }, "newText": "process_charge" }
    ],
    "file:///path/api/routes.py": [ ... ]
  }
}
```

## Dependencies & assumptions

- Python 3.11+
- `pygls` for LSP client protocol handling (or implement JSON-RPC manually)
- An LSP server binary for each language (e.g., `pyright`, `rust-analyzer`, `clangd`, `gopls`) — must be installed separately and locatable on PATH
- `mcp` Python package for MCP server registration
- `pydantic` for tool parameter validation
- The project root must be a real directory on disk; the LSP needs to read files directly
- The agent must call `open_project(root_path)` before any symbol operations; this starts the LSP servers

## To port this, you need:
- [ ] An LSP client that can talk to language server processes (send/receive JSON-RPC over stdio or socket). `pygls` covers this, or use `solidlsp` from Serena directly.
- [ ] A `SymbolRetriever` that wraps LSP calls into `find()`, `find_referencing_symbols()`, `get_diagnostics()`.
- [ ] A `CodeEditor` that performs text edits via `textDocument/didChange` and writes back to disk.
- [ ] Name-path addressing so agents can address symbols as `"ClassName/method"` rather than line numbers.
- [ ] At least one LSP server installed for each language you plan to support.
- [ ] MCP tool wrappers exposing: `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `find_implementations`, `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol`, `safe_delete_symbol`, `get_diagnostics_for_file`.
- [ ] Result truncation on every read tool (`max_answer_chars`) so large codebases don't exhaust context.
- [ ] A warmup delay (1–3s) before the first cross-file reference query — some LSP servers need time to fully index.

## Gotchas

**Diagnostic timing is async.** After editing, diagnostics arrive via a push notification, not synchronously. You must either poll the cache with a timeout, or use pull diagnostics (`textDocument/diagnostic` — not all servers support it). Don't assume diagnostics are immediately current after an edit.

**File buffer drift.** The LSP tracks file state via `didOpen`/`didChange`/`didClose`. If you write to disk without sending `didChange`, the LSP model diverges from the file. Always go through the LSP client for edits; never write the file directly while an LSP session is active.

**Symbol kind enumeration varies.** LSP's `SymbolKind` numbers differ slightly between servers (some call lambdas `Function`, others `Variable`). Normalize kinds to string names early so filtering is portable.

**Cross-file rename edge cases.** LSP rename edits can include file rename operations (not just text edits) when a module file is renamed. Check `WorkspaceEdit.documentChanges` for `RenameFile` / `CreateFile` operations and handle them separately.

**LSP server crash.** Long-running sessions can see the LSP process crash. Implement health checking: periodically send a lightweight request and restart the server if it times out. Serena calls this `_ensure_functional_ls()`.

**Large symbol trees.** A file with 1,000 symbols serializes to megabytes. Apply depth limits (`depth=1` for orientation, `depth=2` for detail) and string length caps before returning to the agent.

**Safe delete is conservative by design.** `safe_delete` only checks references via the LSP — it won't catch dynamic calls (e.g., `getattr(obj, "method_name")`). Warn the agent that dynamic usage is not detected.

## Origin (reference only)
Repo: https://github.com/oraios/serena — files `src/serena/tools/symbol_tools.py`, `src/serena/symbol.py`, `src/serena/code_editor.py`, `src/solidlsp/ls.py`, `src/serena/ls_manager.py`. The `solidlsp` package is their synchronous LSP wrapper built on `pygls`. If the repo is still reachable, `LanguageServerSymbolRetriever` and `LanguageServerCodeEditor` are the classes to read first.
