# Plugin System (build spec) — distilled from markitdown

## Summary

Entry-point-based third-party plugin discovery. Host defines an `importlib.metadata` group (`"markitdown.plugin"`), discovers all installed packages that declare an entry point in that group, loads them lazily with fault isolation, and calls `register_converters(host_instance, **kwargs)` on each. Plugins declare `__plugin_interface_version__ = 1` for forward compatibility.

## Core logic (inlined)

```python
from importlib.metadata import entry_points
from warnings import warn
from typing import List, Any, Optional

_plugins: Optional[List[Any]] = None  # module-level cache

PLUGIN_GROUP = "markitdown.plugin"

def _load_plugins() -> List[Any]:
    global _plugins
    if _plugins is not None:
        return _plugins
    _plugins = []
    for ep in entry_points(group=PLUGIN_GROUP):
        try:
            module = ep.load()
            _plugins.append(module)
        except Exception as e:
            warn(f"Plugin '{ep.name}' failed to load ({e}), skipping.")
    return _plugins

class MarkItDown:
    def __init__(self, enable_plugins: bool = False, **kwargs):
        self._converters = []
        self._register_builtin_converters()
        if enable_plugins:
            self.enable_plugins(**kwargs)

    def enable_plugins(self, **kwargs):
        for plugin in _load_plugins():
            try:
                plugin.register_converters(self, **kwargs)
            except Exception as e:
                warn(f"Plugin {plugin} failed during register_converters: {e}")
```

```toml
# Plugin package's pyproject.toml declares itself:
[project.entry-points."markitdown.plugin"]
my_plugin = "my_package.plugin_module"
```

```python
# Plugin module (my_package/plugin_module.py):
__plugin_interface_version__ = 1

def register_converters(markitdown, **kwargs):
    api_key = kwargs.get("my_plugin_api_key")
    markitdown.register_converter(MyConverter(api_key=api_key))

class MyConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs): ...
    def convert(self, stream, stream_info, **kwargs): ...
```

## Data contracts

- **Entry point group**: `"markitdown.plugin"` (or your own group name — just keep it consistent)
- **Plugin module must export**:
  - `__plugin_interface_version__: int = 1`
  - `register_converters(host_instance, **kwargs) -> None`
- **kwargs forwarding**: host passes init-time kwargs to `register_converters` — use this to pass secrets/config

## Dependencies & assumptions

- Python 3.10+ (`importlib.metadata` entry_points with `group=` kwarg is 3.9+)
- Plugin packages must be installed in the same Python environment as the host
- No dynamic path loading — plugins must be proper packages

## To port this, you need:

- [ ] Choose an entry point group name (e.g., `"myapp.plugin"`)
- [ ] `_load_plugins()` function with module-level list cache
- [ ] `entry_points(group=GROUP)` iteration with try/except per plugin (fault isolation)
- [ ] `enable_plugins(**kwargs)` method on host that calls `plugin.register_converters(self, **kwargs)`
- [ ] `__plugin_interface_version__` convention in your plugin contract docs
- [ ] `[project.entry-points."myapp.plugin"]` section in plugin `pyproject.toml`

## Gotchas

- `_plugins` is a module-level global — all `MarkItDown` instances share the same loaded plugin list. Plugin loading is not per-instance.
- `entry_points(group=...)` only finds installed packages. Local source directories must be installed (`pip install -e .`) to appear.
- `ep.load()` imports the module. Import-time errors (missing deps, syntax errors) are caught by the fault-isolation try/except.
- kwargs forwarding to `register_converters` is how you pass API keys. Document which kwargs each plugin accepts.

## Origin

https://github.com/microsoft/markitdown — `packages/markitdown/src/markitdown/_markitdown.py`, `packages/markitdown-sample-plugin/`
