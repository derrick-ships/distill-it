# Visualization Auto-Selection (build spec) — distilled from metabase

## Summary

A frontend **registry** of chart types where each visualization self-describes its applicability. A
result set is matched against every registered viz's `isSensible(data)` to produce the list of sensible
chart types; the chosen one's `checkRenderable` validates the data (with a user-facing reason) and the
component renders with column **remapping** (FK id → label) and optional multi-series transforms.

## Core logic (inlined)

### Registry (`frontend/src/metabase/visualizations/index.ts`)

```ts
const visualizations = new Map<VisualizationDisplay, Visualization>();   // identifier -> component
const aliases = new Map<string, Visualization>();
let defaultVisualization: Visualization;

export function registerVisualization(visualization: Visualization) {
  const identifier = visualization.identifier;          // static on the component, e.g. "bar"
  if (identifier == null) throw new Error("Visualization must define an 'identifier' static variable");
  if (visualizations.has(identifier)) throw new Error("already registered: " + identifier);
  visualizations.set(identifier, visualization);
  (visualization.aliases ?? []).forEach(a => aliases.set(a, visualization));
}
export function setDefaultVisualization(v: Visualization) { defaultVisualization = v; }
export function getVisualization(display) { return visualizations.get(display) ?? aliases.get(display); }

// THE PICKER: which chart types make sense for this result set?
export function getSensibleDisplays(data: DatasetData): string[] {
  return Array.from(visualizations.values())
    .filter(viz => viz.isSensible?.(data))              // each chart answers for itself
    .map(viz => viz.identifier);
}
```

### Per-visualization contract (each chart component)

```ts
class BarChart extends Component {
  static identifier = "bar";
  static aliases = [];
  static iconName = "bar";
  static isSensible(data: DatasetData): boolean {       // offer this chart?
    const { cols, rows } = data;
    return rows.length > 1 && getColumnCardinality(...) && hasOneDimensionTwoMetrics(cols); // example heuristic
  }
  static checkRenderable(series, settings): void {       // can the CHOSEN data render? throw w/ reason
    if (series[0].data.cols.length < 2) throw new MinColumnsError(2, series[0].data.cols.length);
  }
  static settings = { /* default viz settings */ };
  static maxMetricsSupported = 20;
  static maxDimensionsSupported = 2;
  static defaultSize = { width: 4, height: 3 };
}
registerVisualization(BarChart);
```

### Resolve + transform + remap

```ts
export function getVisualizationRaw(series)        { return getVisualization(series[0].card.display); }
export function getVisualizationTransformed(series){ // combine multiple series into one logical viz
  const viz = getVisualizationRaw(series);
  const { series: t } = viz.transformSeries?.(series) ?? { series };
  return { visualization: viz, series: t };
}
export const extractRemappedColumns = (data) => /* swap FK columns for their remapped_to label */;
export function getMaxMetricsSupported(display)   { return getVisualization(display)?.maxMetricsSupported ?? 1; }
export function getMaxDimensionsSupported(display){ return getVisualization(display)?.maxDimensionsSupported ?? 2; }
export function isCartesianChart(display)         { return CARTESIAN.has(display); }
export function getDefaultSize(display)           { return getVisualization(display)?.defaultSize; }
```

### Flow

```
result set (cols + rows + metadata)
  -> getSensibleDisplays(data)  -> [ "line","bar","table",... ]   (each viz.isSensible)
  -> UI shows sensible types + a default; user picks `display`
  -> getVisualizationTransformed(series) -> { visualization, series }   (multi-series combine)
  -> visualization.checkRenderable(series, settings)  -> throws friendly error if not drawable
  -> render component with extractRemappedColumns(data) applied (FK id -> label)
```

## Data contracts

- **Visualization (static):** `{ identifier, aliases?, iconName, isSensible(data):bool, checkRenderable(series,settings):void|throw, settings, maxMetricsSupported, maxDimensionsSupported, defaultSize, transformSeries? }`.
- **DatasetData:** `{ cols: Column[], rows: any[][], ... }`; **Column:** `{ name, base_type, semantic_type, remapped_to?, remapped_from? }`.
- **Series:** `[{ card:{display, ...}, data: DatasetData }...]`.
- **getSensibleDisplays(data) -> identifier[]**.

## Dependencies & assumptions

- A component framework (React) + a module-load-time registry (each chart calls `registerVisualization`
  on import). Column metadata from the query result (semantic types, remapping). No backend dependency
  for selection itself.
- Swappable: the registry+predicate pattern is framework-agnostic; the heuristics are BI-specific.

## To port this, you need:

- [ ] A registry mapping a stable `identifier` → visualization, populated at load (reject duplicates; support aliases).
- [ ] Per-visualization `isSensible(data)` (offer?) and `checkRenderable(series,settings)` (draw? + reason) predicates.
- [ ] `getSensibleDisplays(data)` = filter the registry by `isSensible`.
- [ ] Declared metrics/dimensions limits + default size per chart for the UI.
- [ ] Column **remapping** (FK id → label) applied at render, and optional multi-series transforms.

## Gotchas

- **Push applicability into each chart** (`isSensible`) — a central switch becomes unmaintainable as chart types grow.
- **Two gates, two purposes** — `isSensible` filters the picker; `checkRenderable` blocks a bad current selection with a message. Don't conflate.
- **Reference charts by stable string id**, not class — saved questions persist the identifier across refactors (hence aliases for renames).
- **Remap at render** — charts must show human labels, not raw FK ids; forgetting the remapping shows ids.
- **Declare metric/dimension caps** so the UI prevents invalid configurations rather than rendering garbage.
- **Default + sensible list** — always provide a sane default display so a fresh result renders without user choice.

## Origin (reference only)

metabase/metabase @ `master`: `frontend/src/metabase/visualizations/index.ts` (registry + selection — inlined),
`frontend/src/metabase/visualizations/visualizations/*` (per-chart `isSensible`/`checkRenderable`),
`frontend/src/metabase/visualizations/lib/{series,settings,warnings}.ts`.

**Gaps to verify (cost-capped):** exact `isSensible` heuristics per chart; `transformSeries` combine
logic; `checkRenderable` error types; how the default display is chosen when several are sensible.
