# Capability-Based Module System — from [vlc](https://code.videolan.org/videolan/vlc)

> Domain: [[plugin-architecture]] · Source: https://code.videolan.org/videolan/vlc · NotebookLM:

## What it does

VLC is built almost entirely from swappable modules (plugins). Everything that isn't the tiny core framework — every codec, every audio output, every network protocol, every user interface, every filter — is a module that gets loaded at runtime and selected by capability. When VLC needs to decode H.264 video, it doesn't call a fixed function. It broadcasts: "I need something capable of `video decoder`," collects every module that claims that capability, scores them by priority, and loads the highest-scoring one that succeeds. If that one fails, it tries the next. The entire product is orchestrated this way.

## Why it exists

VLC runs on Windows, macOS, Linux, Android, iOS, and more. Each platform has different audio APIs, video output APIs, and GPU hardware. A monolithic build would require a maze of `#ifdef` blocks throughout the codebase. Instead, VLC's module system lets platform-specific implementations live in isolation — a module that requires DirectX will simply not be available on macOS, and VLC's core never needs to know about it. The same mechanism also lets third parties ship external `.so`/`.dll` plugins that VLC discovers at startup without recompiling.

## How it actually works

**Module definition.** Each plugin file uses macros to declare itself: `vlc_module_begin()` / `vlc_module_end()` frame the declaration. Inside, the developer calls `set_capability("video decoder", 100)` to announce what the module can do and how confidently it can do it (100 = high priority). `set_description()` names it for UIs. `set_callbacks(Open, Close)` registers the entry and exit functions. A single `.c` file can define multiple sub-modules with `add_submodule()` — for example, one file might provide both an HTTP access module and an HTTPS access module.

**Capability matching.** When VLC's core needs a module, it calls `module_need(obj, "video decoder", "preferred-name,any", true)`. This:
1. Collects all loaded modules that have the requested capability.
2. Sorts them by descending priority score.
3. In strict mode, only considers modules whose names match the comma-separated name list. The keyword `any` disables strict mode and admits all positive-score candidates. The keyword `none` aborts immediately.
4. Iterates through candidates in order. For each, it maps the plugin into memory (`vlc_module_map()`), calls the module's activation function, and returns on the first `VLC_SUCCESS`.

**Selection stored on the object.** When a module is successfully loaded, its name is stored in the parent VLC object's variable system. This means the selection is introspectable and can be overridden by the user passing `--video-decoder=specific_module` on the command line.

**Unloading.** `module_unneed()` calls the deactivation hook and clears the stored reference. Modules are designed to be loaded and unloaded multiple times during a session.

**Configuration options.** Each module can register typed options — strings, integers, floats, booleans — directly in its declaration block using `add_string()`, `add_integer()`, etc. These appear automatically in VLC's preferences UI for the appropriate module. `change_private()` hides an option from the GUI but keeps it accessible via CLI.

## The non-obvious parts

**Score ≠ quality, score = deployment priority.** The score is set by the developer to express "try me first." A platform-native codec (e.g., VideoToolbox on macOS) gets a high score to pre-empt the software fallback (e.g., FFmpeg's avcodec). This is a static preference, not a runtime benchmark.

**The `any` keyword is the default.** Most VLC calls pass `"any"` to mean "I don't care which implementation, give me whatever works." This is what makes the module system feel like magic: you get hardware acceleration automatically if available and software decoding as a seamless fallback, with no conditional code in the consumer.

**Plugin discovery is startup-time, loading is on-demand.** VLC scans plugin directories at startup to build its capability registry (just reading metadata, not full loading). Actual `.so`/`.dll` mapping happens only when `module_need()` is called.

**One file, many modules.** A codec plugin for FFmpeg (`avcodec`) declares hundreds of capabilities (one for each codec it supports) inside a single shared library. The `add_submodule()` macro lets this work without hundreds of separate files.

**Error propagation.** If all candidates fail, `module_need()` returns NULL and VLC logs that no module matched. The caller decides what to do — some errors are fatal, others graceful (e.g., "no subtitle renderer" is tolerable).

## Related

- [[media-pipeline--from-vlc]] (the module system is the engine; the pipeline is what calls it)
- [[plugin-system--from-markitdown]] (Python entry_points–based discovery vs VLC's C capability system — different language, same concept)
- [[register-extensibility-api--from-style-dictionary]] (similar registry pattern, but JS and static rather than C and dynamic)
