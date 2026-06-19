# Visualization Auto-Selection — from [metabase](https://github.com/metabase/metabase)

> Domain: [[_domain]] · Source: https://github.com/metabase/metabase · NotebookLM: <link once added>

## What it does

When a query returns a result set, Metabase decides *how to draw it* — table, bar, line, pie, map,
scalar number — and only offers the chart types that actually make sense for that shape of data. Two
numeric columns over a date? It'll suggest a line chart. A single number? A "big number" scalar. The
frontend has a registry of every visualization, and each one knows whether it's "sensible" for a given
result.

## Why it exists

A BI tool can't make the user hand-configure axes for every question — that's friction that kills
adoption. Auto-selection (and auto-*filtering* of inapplicable chart types) is what makes "ask a
question, get a chart" feel instant. It also keeps the product extensible: new chart types plug into the
same registry and answer the same "are you sensible here?" question, so they slot into the picker
automatically.

## How it actually works

There's a central **registry** — a map from a visualization's `identifier` (e.g. `"bar"`, `"line"`,
`"scalar"`, `"table"`) to the visualization component. Each visualization is a React component that also
carries **static metadata and predicates**: an `isSensible(data)` that says whether this chart makes
sense for a given result set, a `checkRenderable(...)` that throws a helpful error if the chosen data
can't be drawn this way, the max number of metrics and dimensions it supports, default settings, and a
default size.

Key functions over the registry:
- `registerVisualization(viz)` — add a chart type (rejects duplicate identifiers).
- `getSensibleDisplays(data)` — given a result set, return the list of chart types whose `isSensible`
  returns true. This is what populates the "sensible" section of the chart picker.
- `getVisualizationRaw` / `getVisualizationTransformed` — resolve a series to its visualization,
  applying any transforms (e.g. combining multiple series, extracting remapped columns).
- Helpers like `getMaxMetricsSupported`, `getMaxDimensionsSupported`, `isCartesianChart`,
  `getDefaultSize`, `canSavePng`, and `getIconForVisualizationType` drive the UI around the chart.

So the flow is: result set → ask every registered viz `isSensible?` → present the sensible ones (with a
default) → when one is chosen, `checkRenderable` validates and the component renders, with column
**remapping** applied (e.g. show a category name instead of its foreign-key id).

## The non-obvious parts

- **Each chart self-describes its applicability.** The intelligence isn't a big central `if/else`;
  every visualization answers `isSensible(data)` for itself, so the picker is just "filter the registry."
- **Registry by identifier, with alias support.** Charts register under a stable id (and aliases), so
  saved questions reference a string, not a class — stable across refactors.
- **`isSensible` vs `checkRenderable` are two gates.** One decides whether to *offer* a chart; the other
  decides whether the *currently chosen* data can be drawn, with a user-facing reason if not.
- **Metrics/dimensions limits are declared per chart** so the UI can stop you from adding a 4th series
  to something that supports two.
- **Remapping happens at render** — foreign-key columns are swapped for their human label via an
  extracted remapping map, so charts show names, not ids.
- **Series transforms** let one logical visualization combine multiple result series (multi-series line)
  through `getVisualizationTransformed`.

## Related
- [[query-processor-middleware-pipeline--from-metabase]] (produces the result set + column metadata the picker reads)
- [[mbql-query-ast--from-metabase]] (the query's breakout/aggregation shape hints the sensible charts)
- See also: [[rendering]] and [[graph-rendering]] peers.
