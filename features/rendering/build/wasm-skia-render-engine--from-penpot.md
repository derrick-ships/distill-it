# WASM/Skia Render Engine (build spec) — distilled from penpot

## Summary
A canvas renderer for a design tool written in **Rust, compiled to WASM (Emscripten), drawing via
Skia** (rust-skia) onto a single GPU/GL-backed surface. The browser never draws; it drives the engine
through a **C-ABI function interface** (numbers + pointers only) using two patterns: a **"current
shape" + setters** turtle API for scalar props, and **packed binary structs in shared linear memory**
(alloc → write fixed-size records → call a reader fn → free) for bulk data. Rendering is **tile-based
and incremental** with a frame-spread render loop and cheap per-shape transform "modifiers" for
interactive drags. The transplant value is the FFI/serialization architecture, not the Skia calls.

## Core logic (inlined)

### Module layout (`render-wasm/src/`)
`main.rs` (entry + most `#[no_mangle]` exports), `wapi.rs` (JS-imported callbacks, e.g.
`wapi_notifyTilesRenderComplete`), `render/` (pipeline), `render.rs`, `tiles.rs` (tiling),
`shapes/` + `shapes.rs` (shape model + binary decode), `state/` + `state.rs` (global render state),
`fonts/`, `math/`, `view.rs` (viewport), `performance.rs`, `emscripten.rs`.

### The exported C-ABI (browser → engine) — representative signatures
```rust
#[no_mangle] pub extern "C" fn init(width: i32, height: i32) -> ...;
#[no_mangle] pub extern "C" fn set_canvas_background(raw_color: u32) -> Result<()>;
#[no_mangle] pub extern "C" fn resize_viewbox(width: i32, height: i32) -> Result<()>;
#[no_mangle] pub extern "C" fn set_view(zoom: f32, x: f32, y: f32) -> ...;

// "current shape" + setters (a uuid is passed as 4 u32 words)
#[no_mangle] pub extern "C" fn use_shape(a: u32, b: u32, c: u32, d: u32) -> Result<()>;
#[no_mangle] pub extern "C" fn set_shape_transform(a: f32,b: f32,c: f32,d: f32,e: f32,f: f32);
#[no_mangle] pub extern "C" fn set_shape_opacity(opacity: f32) -> Result<()>;
// ...set_shape_kind, set_shape_blend_mode, set_shape_blur, set_shape_corners, etc.

// bulk data via shared memory (no args: the fn reads the pre-written buffer)
#[no_mangle] pub extern "C" fn set_children() -> Result<()>;   // parses UUID chunks, then mem::free_bytes()
#[no_mangle] pub extern "C" fn set_shape_fills() -> Result<()>;// 160-byte fill records
#[no_mangle] pub extern "C" fn set_shape_path_content() -> ...;// 28-byte path segments
#[no_mangle] pub extern "C" fn set_modifiers() -> Result<()>;  // TransformEntry chunks -> HashMap

// the frame
#[no_mangle] pub extern "C" fn render(timestamp: i32, flags: u8) -> Result<FrameType>;
// rebuilds tiles, handles modifier invalidation mid-transform, then
// start_render_loop / continue_render_loop based on flags.

// read-back: return a pointer into linear memory for JS to read
#[no_mangle] pub extern "C" fn get_selection_rect() -> Result<*mut u8>;          // mem::write_bytes(..)
#[no_mangle] pub extern "C" fn render_shape_pixels(a:u32,b:u32,c:u32,d:u32, scale:f32) -> Result<*mut u8>;
```

### Global state access pattern
```rust
// no raw `static mut STATE` in callers; everything goes through macros:
with_state!(state, { state.loading = true; });            // mutable engine state
with_current_shape_mut!(shape, { shape.opacity = opacity; }); // the shape selected by use_shape()
```

### Shared-memory transfer protocol (the reusable core)
JS side (conceptual):
```js
const ptr = Module._alloc_bytes(byteLen);          // engine allocs in WASM linear memory, returns offset
new Uint8Array(Module.HEAPU8.buffer, ptr, byteLen).set(packedBytes); // write packed records
Module._set_shape_fills();                          // engine reads mem::bytes(), parses, frees
```
Rust side (conceptual):
```rust
#[no_mangle] pub extern "C" fn set_shape_fills() -> Result<()> {
    let bytes = mem::bytes();                        // borrow the buffer JS just wrote
    let fills = bytes.chunks_exact(160).map(Fill::from_bytes).collect::<Vec<_>>();
    with_current_shape_mut!(s, { s.fills = fills; });
    mem::free_bytes();                               // release
    Ok(())
}
```

### Binary layouts (from `render-wasm/docs/serialization.md`) — fixed-size records
- **Shape type** = `u8`: `0 Frame, 1 Group, 2 Bool, 3 Rect, 4 Path, 5 Text, 6 Circle, 7 SvgRaw, 8 Image`.
- **Constraints / alignment / stroke caps / linejoins / flex / grid** = `u8` enums.
- **Path segment = 28 bytes:** `command u16 @0, flags u16 @2, c1_x f32 @4, c1_y @8, c2_x @12,
  c2_y @16, x @20, y @24` (cubic control pts + endpoint; command selects move/line/curve/close).
- **Fill = 160 bytes (uniform):** discriminator + payload reused per type (solid color | image ref |
  gradient stops). Uniform size → index by `i*160`, no per-record length prefix.
- UUIDs travel as 4×`u32` (16 bytes) both as args (`use_shape`) and in buffers (`set_children`).

### Tiling + render loop
World is split into tiles; `render()` rebuilds the dirty tile set and re-renders only changed/visible
tiles, spreading long renders across frames via `start_render_loop`/`continue_render_loop`, and calls
back into JS (`wapi_notifyTilesRenderComplete`) when done. Interactive drags push per-shape
`TransformEntry` modifiers (via `set_modifiers`) applied at render time, committed to real state only
at gesture end.

## Data contracts
- **Boundary types:** only `i32/u32/f32` scalars and `*mut u8`/`*const u8` pointers (WASM ABI limit).
- **uuid:** 4×u32. **transform:** 6×f32 (2x3 affine `a b c d e f`). **color:** packed `u32` ARGB.
- **Buffers:** arrays of fixed-size records (28-byte path seg, 160-byte fill, 16-byte uuid,
  TransformEntry for modifiers); engine owns alloc/free.
- **Render flags:** `u8` bitfield to `render(timestamp, flags)`; returns a `FrameType`.
- **Read-back:** functions return a pointer; JS reads N bytes from `HEAPU8` at that offset.

## Dependencies & assumptions
- Rust + `rust-skia` (Skia), built with Emscripten target `wasm32-unknown-emscripten` (emits `.wasm`
  **and** JS glue + shared-memory wiring). A WebGL/GL context for GPU-backed Skia surface.
- Frontend loads the glue, owns `HEAPU8`, and orchestrates alloc/write/call/free.
- Feature-flagged (`enable-feature-render-wasm`, `enable-render-wasm-dpr`) to run beside a legacy SVG renderer.
- Swappable: CanvasKit (Skia's official WASM build) instead of rust-skia if you don't want a Rust toolchain;
  the FFI/serialization patterns are what transfer.

## To port this, you need:
- [ ] A C-ABI surface that only passes scalars + pointers (no rich objects across WASM).
- [ ] An allocator pair (`alloc_bytes`/`free_bytes`) so JS can write into the module's linear memory.
- [ ] **Fixed-size binary record layouts** for bulk data (shapes, paths, fills, ids) — document the bytes.
- [ ] A "current target + setters" pattern (or equivalent) to avoid marshalling whole objects per call.
- [ ] A GPU-backed Skia/CanvasKit surface + viewport (zoom/pan) transform.
- [ ] Tile-based dirty-region rendering + a frame-spread render loop for large scenes.
- [ ] Interactive "modifier" deltas applied at render time, committed only on gesture end.

## Gotchas
- **`HEAPU8.buffer` detaches when WASM memory grows** — re-create typed-array views after any alloc
  that triggers growth, or you'll read/write a stale/detached buffer (classic Emscripten bug).
- **Ownership of buffers must be explicit:** engine allocs, JS writes, engine reads **and frees**.
  Double-free or read-after-free corrupts memory silently. Match every `alloc_bytes` with one `free_bytes`.
- Uniform record sizes (160-byte fills even when unused) trade space for O(1) indexing — keep them
  uniform; variable-length records need length prefixes and kill the memcpy speed.
- Endianness/alignment: pack with explicit offsets (as documented) and the same byte order both sides;
  don't rely on struct auto-layout matching across the boundary.
- The boundary can't return structs — return a pointer and have JS read a known byte count, or pass an
  out-buffer. `Result<*mut u8>` here is exactly that.
- Tile invalidation correctness is the hard part: miss a dirty tile → stale pixels; over-invalidate →
  no perf win. Track changed bounds precisely (incl. blur/stroke overflow into neighboring tiles).
- Don't block the main thread: long renders must yield via the render loop, not one giant synchronous call.

## Origin (reference only)
`render-wasm/src/main.rs` (exported `#[no_mangle]` fns, `with_state!`/`with_current_shape_mut!`,
alloc/free + `mem::bytes()`), `render-wasm/src/wapi.rs` (JS-imported callbacks),
`render-wasm/src/tiles.rs` + `render.rs` (tiling + loop), `render-wasm/docs/serialization.md`
(byte layouts), `render-wasm/README.md` (build/Emscripten/Skia/flags). Frontend integration behind
`enable-feature-render-wasm`.
