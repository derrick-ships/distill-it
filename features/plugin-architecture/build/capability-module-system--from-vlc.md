# Capability-Based Module System (build spec) — distilled from vlc

## Summary

A runtime capability registry where producers declare `(capability_string, priority_int)` and consumers call `load_by_capability(cap, preferences)` and get the best available implementation — with automatic fallback through candidates in priority order. Every major subsystem (codec, output, UI, network) is a "plugin" selected this way; the core never hardcodes implementations.

## Core logic (inlined)

**Module declaration (C macros, simplified):**
```c
vlc_module_begin()
    set_description("My H.264 Decoder")
    set_capability("video decoder", 750)   // cap string + priority score
    set_callbacks(Open, Close)             // activate / deactivate
    add_submodule()
        set_capability("video decoder", 500)  // second capability in same file
        set_callbacks(OpenSW, Close)
vlc_module_end()
```

**Capability matching pseudocode:**
```
function module_need(obj, capability, name_hint, strict):
    candidates = all_modules_with_capability(capability)
    sort candidates by descending priority score

    if strict:
        candidates = filter to those matching name_hint
        // "any" in name_hint disables this filter
        // "none" in name_hint returns NULL immediately

    for each candidate in candidates:
        map_shared_library(candidate)          // dlopen if not already loaded
        result = candidate.activate(obj, ...)  // call Open()
        if result == VLC_SUCCESS:
            obj.loaded_module = candidate.name
            return candidate
        unmap_if_not_needed(candidate)

    log("no module matched capability=%s", capability)
    return NULL
```

**Capability option registration (per module, happens at startup):**
```c
// Inside vlc_module_begin() block:
add_string("my-decoder-codec", "auto", "Codec hint", "Codec hint long", false)
add_integer("my-decoder-threads", 4, "Thread count", NULL, false)
    change_integer_range(1, 64)
add_bool("my-decoder-hw-accel", true, "Use HW accel", NULL, false)
    change_private()   // hides from GUI but keeps CLI-accessible
```

**Unloading:**
```c
module_unneed(obj, module_handle)
// calls module.deactivate(obj) then clears obj.loaded_module
```

## Data contracts

```c
// Module descriptor (stored in registry at startup):
struct vlc_plugin_t {
    const char *psz_capability;   // e.g. "video decoder"
    int         i_score;          // priority (higher = tried first)
    const char *psz_shortname;    // e.g. "avcodec"
    int       (*pf_activate)(...);
    void      (*pf_deactivate)(...);
    // linked list of config_item_t for options
};

// Config option types registered in module:
// VLC_VAR_STRING, VLC_VAR_INTEGER, VLC_VAR_FLOAT, VLC_VAR_BOOL
// Each has: psz_name, psz_text, psz_longtext, default value
```

**Capability name examples from VLC:**
```
"access"           – network/file protocol handler (http, rtsp, file, dvd…)
"access_demux"     – protocol that also knows its container (HLS, DASH…)
"demux"            – container format parser (mp4, mkv, avi, ts…)
"video decoder"    – decode compressed video to raw frames
"audio decoder"    – decode compressed audio to PCM
"vout display"     – render decoded frames to screen
"audio output"     – send PCM to sound system
"interface"        – user interface (Qt, Cocoa, CLI, RC…)
"stream_out"       – output chain (duplicate, transcode, rtp, file…)
```

## Dependencies & assumptions

- Shared library / DLL support for dynamic loading (`dlopen` / `LoadLibrary`).
- Plugin scan directory at startup (VLC reads `$VLC_PLUGIN_PATH` or platform default).
- Each plugin's `.so`/`.dll` exports a single entry point (`vlc_entry__<name>`) that registers all submodules.
- Optional: user-visible preferences UI (VLC's Qt interface reads registered config items automatically).

**Language mapping for other stacks:**
```
Python: importlib.metadata entry_points per group — same concept
Node.js: npm package.json "exports" + dynamic require() per capability
Rust: trait objects + inventory crate for compile-time registration
Go: interface + init() registration map
```

## To port this, you need:

- [ ] A central capability registry (hashmap: capability_string → sorted list of {priority, factory_fn, name}).
- [ ] A registration API: `register(capability, priority, name, activate_fn, deactivate_fn)`.
- [ ] A load function: `load(capability, preferred_name | "any")` → iterates sorted list, tries each until one succeeds.
- [ ] A plugin scan step: discovers and calls registration code for each plugin file (DSO, package, module).
- [ ] Config item registration per module (optional but highly useful for UIs and CLI overrides).
- [ ] Object-level storage: after successful load, record which module was selected (enables introspection and CLI override).

## Gotchas

**Priority score collisions.** Two competing modules with the same score produce undefined ordering (VLC uses stable sort so insertion order breaks ties, but that's fragile). Design your own tie-breaking rule explicitly.

**Capability string typos are silent.** If you call `module_need(obj, "vidio decoder", ...)` nothing matches and you get NULL — no compile-time check. Use constants, not literals.

**Module activation can have side effects.** `Open()` may open file handles, allocate GPU resources, etc. Always call `module_unneed()` when done — even on partial success.

**Shared library re-entrancy.** One `.so` can back multiple active module instances. Thread-safety within the module is the module author's problem; the loader just calls `activate()`.

**Plugin directory security.** VLC loads every `.so` it finds in the plugin path. On a compromised system, a malicious `.so` in that path is a privilege escalation. Validate plugin paths.

**Dynamic vs. static plugins.** VLC supports both linked-in (compile-time) and external (file-scanned) plugins. For embedding in another app, you usually link everything statically and populate the registry via generated code — no file scan needed.

## Origin (reference only)

- Repo: https://code.videolan.org/videolan/vlc (mirror: https://github.com/videolan/vlc)
- `src/modules/modules.c` — `vlc_module_match()`, `vlc_module_load()`, `module_need()`
- `include/vlc_plugin.h` — all declaration macros
- `modules/` — thousands of example implementations
