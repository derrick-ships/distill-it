# Plugin System — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

MarkItDown's plugin system lets anyone publish a Python package that adds new file format converters without modifying the core library. Install the plugin package, pass `enable_plugins=True` (or `--use-plugins` on the CLI), and your custom converter is automatically discovered and registered.

## Why it exists

Microsoft can't anticipate every file format users might need, and doesn't want to bloat the core package with every possible dependency. The plugin system lets the community extend coverage (OCR, proprietary formats, new web sources) while keeping the main install lightweight.

## How it actually works

**The contract:** A plugin package must export two things at the module level:

1. `__plugin_interface_version__ = 1` — a version constant the host checks to detect ABI mismatches.
2. `register_converters(markitdown_instance, **kwargs)` — a function the host calls, passing the live MarkItDown instance so the plugin can call `instance.register_converter(MyConverter())`.

**Discovery:** MarkItDown uses Python's `importlib.metadata.entry_points()` with `group="markitdown.plugin"`. This is the standard Python entry points mechanism — any installed package that declares an entry point in the `[project.entry-points."markitdown.plugin"]` section of its `pyproject.toml` is automatically found.

**Loading:** Discovery is lazy and cached. The first time `enable_plugins` is requested, `_load_plugins()` runs, iterates all matching entry points, calls `.load()` on each (which imports the module), and caches the list globally. Subsequent `MarkItDown(enable_plugins=True)` instances use the cached list.

**Fault isolation:** If any plugin fails to load, a `warn()` is issued and the plugin is skipped. The host continues loading remaining plugins and proceeds normally. One broken plugin cannot crash the application.

**Registration:** Once loaded, `plugin.register_converters(self, **kwargs)` is called. The plugin receives the live instance and calls `register_converter()` as many times as needed. The kwargs allow passing config (API keys, model names) from the host to the plugin.

## The non-obvious parts

- `__plugin_interface_version__` is a forward-compatibility hook. The host doesn't currently enforce it, but it's there so future breaking changes can be detected and handled gracefully.
- Plugins are installed packages (via pip), not local files. There's no "load from path" mechanism — plugins must be proper Python packages.
- The community convention for publishing plugins is the `#markitdown-plugin` GitHub topic, making them searchable.
- kwargs forwarding to `register_converters` is how plugins receive secrets (e.g., an LLM API key) without hard-coding them.

## Related

- [[converter-pipeline--from-markitdown]] — where plugin converters end up after registration
