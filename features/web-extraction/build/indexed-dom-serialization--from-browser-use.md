# Indexed DOM Serialization (build spec) — distilled from browser-use

## Summary

Build the perception layer for a browser agent: capture a live page over the Chrome DevTools Protocol (CDP), merge DOM + accessibility + layout snapshot data into one enriched node tree, filter it down to *visible interactive* elements, assign each a stable integer index, and render a compact text list for an LLM. Keep a map from index → real node so the model's "click element N" can be executed. Mark elements that are new since the previous observation.

## Core logic (inlined)

### 1. Capture — four parallel CDP calls per observation
```
trees = await gather(
    cdp("DOMSnapshot.captureSnapshot", {computedStyles: REQUIRED_COMPUTED_STYLES, includePaintOrder: true}),
    cdp("DOM.getDocument", {depth: -1, pierce: true}),         # pierce = include shadow roots + iframe docs
    cdp_per_frame("Accessibility.getFullAXTree"),               # merge all frames into one flat array
    cdp("Page.getLayoutMetrics"),                               # device_pixel_ratio
)  # 10s timeout, retry once; if any fail -> raise TimeoutError

REQUIRED_COMPUTED_STYLES = ['display','visibility','opacity','overflow','overflow-x',
    'overflow-y','cursor','pointer-events','position','background-color']  # exactly 10 — more crashes Chrome on heavy pages
```
Also detect real JS click handlers (catches `<div onclick>`):
```
# Runtime.evaluate with includeCommandLineAPI:true so getEventListeners() exists (DevTools-only):
js: document.querySelectorAll('*') -> keep el if getEventListeners(el) has any of
    {click, mousedown, mouseup, pointerdown, pointerup}
# resolve each match to backendNodeId via parallel DOM.describeNode
# SKIP entirely if element count > 10_000 (perf)
=> js_click_listener_backend_ids: set[int]
```

### 2. Build snapshot lookup (keyed by backendNodeId)
```
snapshot_lookup: dict[int, EnhancedSnapshotNode]
# CDP returns columnar/indexed arrays; rare boolean arrays (e.g. isClickable) -> convert to set[int]
# for O(1) membership (documented ~3000x speedup at 20k elements).
# bounds are in CSS px = raw / device_pixel_ratio.
```

### 3. Merge into EnhancedDOMTreeNode tree (recursive, memoized by nodeId)
For each DOM node: attach its AX node (by backendNodeId), attach snapshot node, compute
`absolute_position` by accumulating iframe offsets, set `has_js_click_listener`, recurse into
`contentDocument` (iframes), `shadowRoots`, `children`, then compute visibility.

```
@dataclass EnhancedDOMTreeNode:
    node_id: int                 # per-session, resets on navigation — DO NOT use as the LLM index
    backend_node_id: int         # <-- THIS is the index space exposed to the LLM
    node_type: int               # 1=ELEMENT, 3=TEXT, 11=DOC_FRAGMENT
    node_name: str               # "BUTTON", "#text"
    node_value: str
    attributes: dict[str,str]
    is_scrollable: bool|None
    is_visible: bool|None
    absolute_position: DOMRect|None   # in top-level page coords
    frame_id, target_id, session_id
    content_document: EnhancedDOMTreeNode|None   # iframe body
    shadow_root_type, shadow_roots: list|None
    parent_node, children_nodes: list|None
    ax_node: {role, name, description, properties}|None
    snapshot_node: EnhancedSnapshotNode|None
    has_js_click_listener: bool

EnhancedSnapshotNode:
    bounds: DOMRect          # document coords (ignores scroll)
    clientRects: DOMRect     # viewport coords (includes scroll)
    scrollRects: DOMRect
    computed_styles: dict[str,str]   # the 10 above
    paint_order: int|None
    is_clickable: bool|None  # CDP isClickable
    cursor_style: str|None
```

**Visibility** (`is_visible`): `display != none` AND `visibility != hidden` AND `opacity > 0`,
AND bounds intersect each ancestor HTML-frame viewport expanded by `viewport_threshold` (default
**1000px** above & below), accounting for scroll offsets accumulated through the iframe chain.

**iframe coordinate accumulation** (easy to get wrong): maintain a running `total_frame_offset`;
for each HTML frame node subtract its scroll offset; for each IFRAME element add its `bounds.x/y`.
Result: `absolute_position` is always in the top-level page's coordinate space.
Cross-origin iframes: recurse via a new `get_dom_tree()` on the iframe targetId, depth-guarded
(`max_iframe_depth`=5), skip if <50x50px or invisible. Hard cap `max_iframes`=100.

### 4. Serialize -> selector_map + text
```
def serialize(root, previous_selector_map):
    simplified = create_simplified_tree(root)   # skip {style,script,head,meta,link,title}; collapse SVG;
                                                 # always include shadow roots; synth controls (see below)
    if paint_order_filtering:                    # remove occluded elements
        for node in nodes_sorted_by_paint_order_desc:
            if node.bounds fully covered by union_of_already_seen_rects: node.ignored_by_paint_order=True
            else: add node.bounds to union   # skip transparent bg rgba(0,0,0,0) or opacity<0.8; cap at 5000 rects
    optimize_tree(simplified)                    # drop meaningless wrapper parents
    apply_bbox_filtering(simplified)             # children >=99% inside a button/link/combobox -> excluded_by_parent
    selector_map = {}
    for node in visible(simplified):
        if ClickableElementDetector.is_interactive(node):
            node.is_interactive = True
            selector_map[node.backend_node_id] = node            # <-- key = backendNodeId
            node.is_new = node.backend_node_id not in previous_selector_map.keys()
    text = render(simplified)
    return SerializedDOMState(selector_map=selector_map, root=simplified)  # .llm_representation() -> text
```

**`ClickableElementDetector.is_interactive`** (first match wins):
1. `has_js_click_listener`  2. form control nested in `<label>`/`<span>`
3. tag in `{button,input,select,textarea,a,details,summary,option,optgroup}`
4. ARIA role attr in `{button,link,menuitem,option,radio,checkbox,tab,textbox,combobox,slider,spinbutton,search,searchbox,row,cell,gridcell}`
5. AX-tree role in same set + `listbox`  6. attrs `{onclick,onmousedown,onmouseup,onkeydown,onkeyup,tabindex}`
7. `cursor: pointer`  8. search-related class/id/data attrs  9. `<iframe>` >=100x100px

**Synthesized control children** (so the model can act on compound widgets): file input -> "Browse"
button + "N files selected"; number input -> increment/decrement + value textbox; range -> slider
node w/ min/max; select -> toggle + listbox w/ option count/preview; date/time -> no children, append
"use ISO 8601" hint. Synth children are always `is_new=True`.

**Render format** (depth-indented):
```
[<backend_node_id>]<tag attr="v" ... />     # only DEFAULT_INCLUDE_ATTRIBUTES (~50): type,name,id,role,
*[<backend_node_id>]<tag ... />             #   value,placeholder,aria-label,aria-expanded,checked,
|SHADOW(open)| ... |Shadow End|            #   data-state,pattern,min,max ... ; password value suppressed
# scrollable nodes append scroll state e.g. "scroll: 0.0^ 2.3v 15%"
# * prefix = is_new (appeared since previous observation)
```

### 5. Resolve index -> node -> click
```
def get_dom_element_by_index(i): return cached_selector_map.get(i)   # cache set after each build
# click: get coords from node.absolute_position or DOM.getBoxModel(backendNodeId), scroll into view,
#        Input.dispatchMouseEvent (move->down->up) at center; fallback Runtime.callFunctionOn el.click()
```

## Data contracts

- **Output to the agent:** `SerializedDOMState { selector_map: dict[int -> EnhancedDOMTreeNode] (key=backendNodeId), root: SimplifiedNode }`; `.llm_representation()` -> the text string above.
- **Action input shape:** every action model carries `index: int` (a backendNodeId from the map).
- **Cached on session:** `_cached_selector_map: dict[int, EnhancedDOMTreeNode]` for index resolution.

## Dependencies & assumptions

- A CDP transport (browser-use uses `cdp_use.CDPClient` over WebSocket, not Playwright's API). Any CDP client works; you need `DOMSnapshot`, `DOM`, `Accessibility`, `Page`, `Runtime`, `DOM.describeNode`, `Input`, `DOM.getBoxModel`.
- A Chromium browser reachable via CDP (see [[browser-session-stealth--from-browser-use]]).
- Swappable: the JS-listener detection (DevTools `getEventListeners`) is an enhancement — without it you lose `<div onclick>` detection but the tag/role/cursor heuristics still work.

## To port this, you need:
- [ ] A live CDP connection to a page target.
- [ ] The merge step: join DOM nodes <-> AX nodes <-> snapshot nodes by `backendNodeId`.
- [ ] The interactivity detector (the 9-rule ladder) and the visibility check (styles + viewport+-buffer).
- [ ] A stable index scheme — reuse `backendNodeId`; do NOT invent sequential ids unless you also persist the mapping.
- [ ] An index->node cache and a click executor that converts a node to coordinates.
- [ ] (Optional but high-value) paint-order occlusion filtering and the `*` new-element diff.

## Gotchas

- **`backendNodeId`, not `nodeId`, and not a 1..N counter.** Keying the selector map by `nodeId` breaks across navigations; using a fresh 1..N counter breaks if you don't persist it for the next step's diff. browser-use exposes the raw backendNodeId.
- **Ten computed styles, not more** — Chrome can crash capturing full computed styles on heavy pages.
- **All-or-nothing capture** — the 4 parallel calls share one timeout; one failure fails the step. Consider per-call degradation if you need robustness.
- **Always include shadow DOM** — SPAs hide real content there even when it looks empty.
- **The 1000px buffer** desyncs the model's element list from a literal screenshot; if you also send a screenshot, expect "I see elements that aren't on screen."
- **Paint-order opacity threshold (0.8) is a heuristic** ("vibes-based" per the source) — overlays with opacity 0.8-1.0 will occlude; semi-transparent ones won't.
- **`getEventListeners()` only exists with `includeCommandLineAPI:true`** in a DevTools context, and is disabled >10k elements.
- **Passwords:** suppress `value` on password inputs before serializing.

## Origin (reference only)
Repo: https://github.com/browser-use/browser-use (branch `main`). Files:
`browser_use/dom/service.py` (capture + merge), `browser_use/dom/enhanced_snapshot.py`
(snapshot lookup), `browser_use/dom/views.py` (node dataclasses), `browser_use/dom/serializer/`
(`serializer.py`, `clickable_elements.py`, `paint_order.py`), `browser_use/browser/watchdogs/dom_watchdog.py`
(triggers capture, caches selector_map), `browser_use/browser/watchdogs/default_action_watchdog.py` (click).
Gaps to verify if the repo is reachable: exact scroll-state string template; `python_highlights.py`
overlay behavior; lines 600-4018 of `session.py` (`get_dom_element_by_index`/`update_cached_selector_map` confirmed by query, not line-read).
