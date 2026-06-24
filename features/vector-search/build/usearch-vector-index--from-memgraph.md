# USearch Vector Index (build spec) — distilled from memgraph

## Summary

An embedded ANN (HNSW) index over node/edge embeddings, built on the USearch library (`unum::usearch`), kept consistent with a live transactional store. Each index is a USearch dense index whose key is the **vertex pointer**; per-index config = {metric, dimension, scalar_kind, capacity, resize_coefficient}. A 4-mode membership filter (SINGLE/WILDCARD/ANY_OF/ALL_OF) selects which entities belong. The index registry is a copy-on-write `shared_ptr` for snapshot-stable reads; mutation only under exclusive (UNIQUE) host access; runs at READ_UNCOMMITTED. Drop is fully undo-able; indices serialize into snapshots and recover via WAL replay.

## Core logic (inlined)

### Spec + container

```cpp
struct VectorIndexSpec {
  std::string index_name;
  VectorMembershipFilter<LabelId> label_filter;   // SINGLE/WILDCARD/ANY_OF/ALL_OF + ids
  PropertyId property;                             // which property holds the embedding
  usearch::metric_kind_t metric_kind;             // cos / l2sq / ip / ...
  uint16_t dimension;
  uint16_t resize_coefficient;
  size_t   capacity;
  usearch::scalar_kind_t scalar_kind;             // f32 / f16 / i8 ... (memory vs precision)
};
struct IndexItem { synchronized_mg_vector_index_t mg_index; VectorIndexSpec spec; }; // mg_index wraps usearch index + a mutex
using VectorIndexContainer = std::unordered_map<uint64_t /*index_id*/, std::shared_ptr<IndexItem>>;
// registry held copy-on-write:
std::shared_ptr<VectorIndexContainer> index_ = std::make_shared<VectorIndexContainer>();
```

### Create (build a USearch HNSW, then populate)

```cpp
SetupIndex(spec, name_id_mapper):
  index_id = name_id_mapper->NameToId(spec.index_name)
  if index_->contains(index_id): return nullopt
  if any existing index has same (label_filter, property): return nullopt        // no duplicate
  metric = usearch::metric_punned_t(spec.dimension, spec.metric_kind, spec.scalar_kind)
  limits = usearch::index_limits_t(spec.capacity, GetVectorIndexThreadCount())
  mg_index = mg_vector_index_t::make(metric, {}, {}, tape_alloc{memtracker}, vectors_tape_alloc{memtracker})
  if !mg_index.index.try_reserve(limits): throw VectorSearchException("reserve failed")
  new_map = copy(*index_); new_map->try_emplace(index_id, make_shared<IndexItem>(move(index), spec))
  index_ = new_map                  // COW publish
  return index_id

CreateIndex(spec, vertices, ...):
  id = SetupIndex(spec, ...); if !id: return false
  PopulateVectorIndexSingleThreaded(vertices, [&](Vertex& v, thread_id){ AddVertexToIndex(*id, v, decoder, thread_id); })
  // on any exception: DropIndex(spec.index_name) then rethrow
```

### Add a vertex (filter, then insert into USearch)

```cpp
AddVertexToIndex(index_id, vertex, decoder, thread_id):
  item = index_->at(index_id)
  if !item->spec.label_filter.Matches(vertex.labels): return       // membership filter
  prop = vertex.properties.GetProperty(spec.property, decoder)
  if prop.IsNull(): return
  vector = RegisterIndexId(prop, index_id)        // tag the property value as belonging to this index
  vertex.properties.SetProperty(spec.property, prop)
  UpdateVectorIndex(item->mg_index, spec, &vertex, vector, thread_id)   // -> usearch index.add(key=&vertex, vector)
```

### Search (single USearch call, distance → similarity)

```cpp
SearchNodes(index_name, k, query_vector, name_id_mapper) -> vector<tuple<Vertex*, double dist, double sim>>:
  item = index_->at(NameToId(index_name))
  guard = shared_read_lock(item->mg_index.mutex)
  result_keys = item->mg_index.index.search(query_vector.data(), k)   // USearch ANN
  for r in result_keys:
    vertex = static_cast<Vertex*>(r.member.key)                       // key IS the vertex pointer
    sim = abs(SimilarityFromDistance(metric_kind, r.distance))
    emit (vertex, double(r.distance), sim)
```

### Membership filter (shared node/edge, 4 modes)

```cpp
template <typename IdT> struct VectorMembershipFilter {
  VectorMatchMode mode;  std::vector<IdT> ids;   // enum: SINGLE=0, WILDCARD=1, ANY_OF=2, ALL_OF=3
  bool Matches(span<const IdT> entity_ids) const {
    if (ids.empty() && mode != WILDCARD) return false;
    switch (mode) {
      case WILDCARD: return true;
      case SINGLE:   return contains(entity_ids, ids[0]);
      case ANY_OF:   return any_of(ids, [&](id){ return contains(entity_ids, id); });
      case ALL_OF:   return all_of(ids, [&](id){ return contains(entity_ids, id); });
    }
  }
  bool IsAffectedBy(IdT id) const { return mode != WILDCARD && contains(ids, id); }
  // Format(): WILDCARD->"*", SINGLE->":L", ANY_OF->":A|B", ALL_OF->":A&B"
};
```

### Undo-able drop (capture enough to reinstall on abort)

```cpp
DropIndex(index_name) -> optional<DroppedIndexCapture>:
  item = index_->at(id)                       // keep alive (its usearch state)
  guard = lock(item->mg_index.mutex)
  keys = export_keys(item->index)             // all indexed vertices
  rewritten = []
  try (OutOfMemoryExceptionEnabler):
    for v in keys:
      pv = v->properties.GetProperty(spec.property)
      if UnregisterIndexId(pv, id):           // last index on this prop -> demote vector to a plain property
        item->index.get(v, buf); v->properties.SetProperty(spec.property, PropertyValue(buf))
      else: v->properties.SetProperty(spec.property, pv)
      rewritten.push_back(v)
  catch OOM:
    for v in rewritten: ReinstallIndexIdInProperty(v, spec.property, id)   // rollback partial rewrite
    throw
  new_map = copy(*index_); new_map->erase(id); index_ = new_map           // COW publish removal
  return { index_id=id, evicted_item=item, rewritten_vertices=rewritten }

RestoreIndex(capture):   // abort path, noexcept (OutOfMemoryExceptionBlocker)
  for v in capture.rewritten_vertices: ReinstallIndexIdInProperty(v, spec.property, capture.index_id)
  new_map = copy(*index_); new_map->try_emplace(capture.index_id, move(capture.evicted_item)); index_ = new_map
```

### Consistency hooks (called by the storage engine on mutations)

- `UpdateOnAddLabel(label, vertex, decoder)` — if vertex now matches an index's filter, insert it (property value becomes a `VectorIndexIdData{ids, vector}` tagging which indices hold it).
- `UpdateOnRemoveLabel(...)` — if vertex no longer matches, remove from that index; if it was the last index, demote the embedding back to a plain property (preserve data).
- `UpdateOnSetProperty(property, value, vertex)` — re-add to all indices referenced by the value, or remove if the new value isn't an embedding.
- `RemoveVertices(vertices)` — called by GC **before** skip-list removal while the pointer is still valid (the key is the pointer!).
- `AbortEntries(...)` + `AbortProcessor` (l2p/p2l maps, wildcard set) — collect label/property changes during a txn so they can be reversed on abort.

### Durability

- `SerializeAllVectorIndices(encoder, mapped_ids)` — writes each index's spec + every (vertex_gid, vector) into the snapshot.
- `VectorIndexRecovery` — rebuilds indices during WAL replay / snapshot load: `UpdateOnIndexDrop / UpdateOnLabelAddition / UpdateOnLabelRemoval / UpdateOnSetProperty` maintain a `vector<VectorIndexRecoveryInfo>{spec, gid->vector}` so the HNSW can be repopulated single- or multi-threaded (`FLAGS_storage_parallel_schema_recovery`).

## Data contracts

- **VectorIndexInfo** (listing): `{index_name, label_filter, property, metric, dimension, capacity, size, scalar_kind}`.
- **Search result:** `vector<tuple<Vertex*, double distance, double similarity>>`. similarity = `abs(SimilarityFromDistance(metric, distance))`.
- **Property tagging:** an indexed embedding property becomes `VectorIndexIdData{ small_vector<uint64> ids; small_vector<float> vector }` — `ids` are the index ids holding this vertex.
- **WAL record** `WalVectorIndexCreate{index_name, label_filter(mode+ids), property, metric_kind, dimension, resize_coefficient, capacity, scalar_kind}`; also `WalVectorIndexDrop`, `WalVectorEdgeIndexCreate`.

## Dependencies & assumptions

- **USearch** (`unum::usearch`): `metric_punned_t`, `index_limits_t`, `index_dense` — provides `add`, `search`, `get`, `remove`, `export_keys`, `contains`, `dimensions/size/capacity`. This is the ANN engine; swap-in any HNSW lib with the same primitives.
- A host store whose record pointers are stable for the index entry's lifetime (key = `Vertex*`), with a GC that calls `RemoveVertices` before freeing.
- An exclusive ("UNIQUE") host access mode that excludes concurrent readers/writers during `index_` mutation — this is what makes READ_UNCOMMITTED safe.
- A memory tracker for OOM accounting (custom allocators `TrackedVectorAllocator<64>`/`<8>`).
- A durability encoder + recovery framework to (de)serialize indices.

## To port this, you need:
- [ ] An ANN/HNSW library with add/search/remove/export keyed by your record pointer or id.
- [ ] A per-index spec {metric, dimension, scalar_kind, capacity} and a duplicate guard on (filter, property).
- [ ] A copy-on-write registry of indices if you want lock-free, snapshot-stable reads.
- [ ] Mutation only under an exclusive host lock if you forgo per-index MVCC (READ_UNCOMMITTED).
- [ ] Consistency hooks on label/property add/remove and a GC hook to remove entries before the record is freed.
- [ ] (If durable) serialize specs + vectors into your snapshot and a recovery path to rebuild the ANN.
- [ ] A reversible drop if drops can occur inside abortable transactions.

## Gotchas

- **The HNSW key is the live record pointer.** You MUST remove from the index before the record is freed, or search returns dangling pointers. Coordinate with GC.
- **READ_UNCOMMITTED is only safe under the UNIQUE-access invariant.** If your host doesn't exclude readers/writers during index mutation, you need real synchronization or per-index MVCC.
- **Drop is expensive and can OOM.** Converting an index back to per-record properties allocates; wrap it with OOM-aware rollback, and make the abort/restore path `noexcept`.
- **COW publish, don't mutate in place.** Readers hold the old container snapshot; mutate a copy and swap the `shared_ptr`, or you'll corrupt in-flight iterations.
- **scalar_kind trades memory for precision** (f32 vs f16/i8). Picking too small a scalar silently degrades recall.
- **Duplicate-index guard is on (filter, property), not just name.** Two indices over the same label-filter+property are rejected.
- **Distance vs similarity are different numbers.** USearch returns distance; convert per-metric (and `abs`) to a similarity score before surfacing.

## Origin (reference only)

Repo: https://github.com/memgraph/memgraph — `src/storage/v2/indices/vector_index.hpp` + `vector_index.cpp` (VectorIndex, VectorIndexSpec, VectorMembershipFilter, SetupIndex/CreateIndex/AddVertexToIndex/SearchNodes/DropIndex/RestoreIndex/SerializeAllVectorIndices/VectorIndexRecovery), `vector_match_mode.hpp` (the 4 modes), `vector_index_utils.hpp` (UpdateVectorIndex, SimilarityFromDistance, NameFromMetric/Scalar). Built on the USearch library (`usearch/index_dense.hpp`).
