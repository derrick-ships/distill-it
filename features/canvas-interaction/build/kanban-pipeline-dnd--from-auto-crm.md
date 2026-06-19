# Kanban Pipeline (drag-and-drop) (build spec) — distilled from auto-crm

## Summary
A `@dnd-kit` Kanban board of pipeline stages (columns) holding deal cards. Core pattern is
**optimistic update with full-board snapshot rollback**: snapshot on drag start, move card in local
state during `onDragOver`, persist with `PUT /api/pipeline { dealId, stageId }` on `onDragEnd`, and
restore the snapshot + toast on save failure. `PointerSensor` with 8px activation distance separates
clicks from drags; `closestCorners` collision; a `DragOverlay` renders the lifted card. The same PUT
endpoint also bulk-reconfigures stages (`{ stages }`) but only when no deals exist.

## Core logic (inlined)

### Board component (@dnd-kit)
```tsx
import { DndContext, PointerSensor, useSensor, useSensors, closestCorners, DragOverlay } from "@dnd-kit/core";

function KanbanBoard({ initial }: { initial: Stage[] }) {
  const [columns, setColumns] = useState<Stage[]>(initial);      // stages, each with deals[]
  const [activeId, setActiveId] = useState<string | null>(null); // deal being dragged
  const snapshotRef = useRef<Stage[] | null>(null);              // pre-drag rollback state

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }), // 8px => real drag, not a click
  );

  function handleDragStart(e) {
    setActiveId(e.active.id);
    snapshotRef.current = structuredClone(columns);  // keep undo card
  }

  function handleDragOver(e) {
    const { active, over } = e;
    if (!over) return;
    const fromCol = colOf(columns, active.id);
    const toCol   = colIdOf(over);                   // column under cursor
    if (!fromCol || fromCol.id === toCol) return;
    setColumns(prev => moveDealBetweenColumns(prev, active.id, toCol)); // optimistic, live reflow
  }

  async function handleDragEnd(e) {
    const dealId = e.active.id;
    const stageId = colIdOf(e.over);
    setActiveId(null);
    if (!stageId) return;
    try {
      const res = await fetch("/api/pipeline", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dealId, stageId }),
      });
      if (!res.ok) throw new Error("save failed");
    } catch {
      if (snapshotRef.current) setColumns(snapshotRef.current);     // total rollback
      toast.error("Error al mover el deal. Se revirtió el cambio.");
    }
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCorners}
      onDragStart={handleDragStart} onDragOver={handleDragOver} onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto">
        {columns.map(col => <KanbanColumn key={col.id} stage={col} deals={col.deals} />)}
      </div>
      <DragOverlay>{activeId ? <DealCard deal={findDeal(columns, activeId)} /> : null}</DragOverlay>
    </DndContext>
  );
}
```
Cards/columns use `useDraggable`/`useDroppable` (or `useSortable`) keyed by deal id / stage id.
`DealCard` reads normalized contact data (either flat `contactName/contactTemperature` or a nested
`contact` object — handle both).

### Persistence endpoint (`PUT /api/pipeline`)
```ts
const body = await req.json().catch(() => null);
if (!body) return Response.json({ error: "JSON inválido" }, { status: 400 });

// (a) single move
if (body.dealId && body.stageId) {
  const deal = db.prepare("SELECT id FROM deals WHERE id=?").get(body.dealId);
  if (!deal) return Response.json({ error: "Deal no encontrado" }, { status: 404 });
  db.prepare("UPDATE deals SET stageId=?, updatedAt=? WHERE id=?").run(body.stageId, Date.now(), body.dealId);
  const updated = db.prepare("SELECT * FROM deals WHERE id=?").get(body.dealId);
  return Response.json(updated);
}

// (b) bulk stage reconfigure — only if NO deals exist (avoid orphaning)
if (Array.isArray(body.stages)) {
  const count = db.prepare("SELECT COUNT(*) n FROM deals").get().n;
  if (count > 0) return Response.json({ error: "No se pueden reemplazar etapas con deals activos" }, { status: 400 });
  db.prepare("DELETE FROM pipelineStages").run();
  for (const s of body.stages)
    db.prepare("INSERT INTO pipelineStages (id,name,\"order\",color,isWon,isLost) VALUES (?,?,?,?,?,?)")
      .run(s.id ?? crypto.randomUUID(), s.name, s.order, s.color ?? "#64748b", s.isWon?1:0, s.isLost?1:0);
  return Response.json(db.prepare('SELECT * FROM pipelineStages ORDER BY "order"').all());
}

return Response.json({ error: "Request inválido" }, { status: 400 });
```

### GET (board data)
`GET /api/pipeline` → all stages `ORDER BY order`, each with nested `deals[]` (deal fields + joined
contact `name`/`temperature`).

## Data contracts
- **Stage:** `{ id, name, order:int, color:hex, isWon:bool, isLost:bool, deals: Deal[] }`
- **Deal:** `{ id, title, value:int, stageId, contactId, probability:int, expectedClose?, notes?,
  contact?: { name, temperature } }`
- **PUT move:** req `{ dealId, stageId }` → `200 Deal` | `404 {error}`.
- **PUT reconfigure:** req `{ stages: Stage[] }` → `200 Stage[]` | `400` if any deal exists.
- **Default seeded stages** (from init): Prospecto(1,#64748b), Contactado(2,#2563eb),
  Propuesta(3,#8b5cf6), Negociación(4,#ea580c), Cerrado Ganado(5,#16a34a, isWon),
  Cerrado Perdido(6,#dc2626, isLost).

## Dependencies & assumptions
- `@dnd-kit/core` (+ `@dnd-kit/sortable` if using sortable lists), React 18/19, a toast lib.
- `deals` + `pipelineStages` tables; deals reference a stage. WAL SQLite or any store.
- Assumes board fits the dnd-kit list/column model (not a free 2D canvas).

## To port this, you need:
- [ ] `@dnd-kit` wired with `PointerSensor` (8px activation) + `closestCorners`.
- [ ] Local board state mirroring stages→deals, plus a `useRef` snapshot for rollback.
- [ ] `onDragStart` (snapshot), `onDragOver` (optimistic move), `onDragEnd` (persist + rollback-on-fail).
- [ ] A `PUT` (or PATCH) endpoint that updates a single deal's stage, validating the deal exists.
- [ ] A toast for the failure path. A `DragOverlay` for the lifted-card feel.
- [ ] Seeded stages with `isWon`/`isLost` flags (analytics depends on them).

## Gotchas
- **Snapshot must be a deep clone.** `structuredClone(columns)` — a shallow copy lets the optimistic
  mutation corrupt your rollback state.
- **Optimistic move belongs in `onDragOver`**, not only `onDragEnd`, or the card won't visibly change
  columns while held.
- **Always reconcile after save** if the server can reorder/normalize — here it trusts the client's
  target stage, but if your server re-sorts, re-fetch or apply the returned deal.
- **The bulk-reconfigure guard is load-bearing.** Allowing stage deletion while deals exist orphans
  `deals.stageId`. Keep the "no deals" precondition (or migrate deals first).
- **8px activation** is tuned for mouse; for touch you may want a delay-based activation instead.
- **Normalize contact shape on the card.** The board passes either flat fields or a nested `contact`;
  read both to avoid `undefined` names.

## Origin (reference only)
auto-crm — `src/components/pipeline/{KanbanBoard,KanbanColumn,DealCard}.tsx`;
`src/app/api/pipeline/route.ts` (GET + dual-purpose PUT); default stages in `scripts/init.ts`.
