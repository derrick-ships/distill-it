# Declarative HTTP Stream Stack (build spec) — distilled from airbyte

## Summary

Four swappable components + a retriever loop pull records from a REST API. **HttpRequester** (build+send
with interpolated url/params/headers + error handler/backoff) → **DefaultPaginator** (strategy computes
next token; option says where to inject it) → **DpathExtractor** (dig records out of decoded JSON via a
`field_path`) → **RecordSelector** (filter + schema-normalize + transform). **SimpleRetriever** loops:
send page → select records → next-page-token → repeat until `None`. Glued by `InterpolatedString`
against `{config, parameters, stream_state, stream_slice, next_page_token}`.

## Core logic (inlined)

### SimpleRetriever loop (`retrievers/simple_retriever.py`)

```python
class SimpleRetriever(Retriever):
    requester: Requester
    record_selector: HttpSelector
    paginator: Optional[Paginator]      # defaults to NoPagination
    stream_slicer / cursor              # supply stream_slice + state

    def read_records(self, records_schema, stream_slice=None):
        # iterate pages for this slice
        for record in self._read_pages(self._parse_records, stream_state, stream_slice):
            yield record

    def _read_pages(self, records_generator_fn, stream_state, stream_slice):
        next_page_token = None
        while True:
            response = self._fetch_next_page(stream_state, stream_slice, next_page_token)   # requester.send_request(...)
            yield from records_generator_fn(response, stream_state, stream_slice)           # selector.select_records
            next_page_token = self._next_page_token(response, ...)                          # paginator.next_page_token
            if not next_page_token:
                break

    def _fetch_next_page(self, stream_state, stream_slice, next_page_token):
        return self.requester.send_request(
            path=self._paginator_path(...),
            request_params=self._request_params(stream_state, stream_slice, next_page_token),
            request_headers=..., request_body_json=..., )

    def _parse_records(self, response, stream_state, stream_slice):
        yield from self.record_selector.select_records(response, stream_state=stream_state, stream_slice=stream_slice, records_schema=...)
```

### HttpRequester (`requesters/http_requester.py`)

```python
class HttpRequester(Requester):
    url_base / path: InterpolatedString          # templates -> embed config/params/state/page_token
    error_handler: Optional[ErrorHandler]        # backoff_strategies live here
    def __post_init__(self, parameters):
        self._url_base = InterpolatedString.create(self.url_base, parameters=parameters)
        self._path     = InterpolatedString.create(self.path, parameters=parameters)
        backoff = self.error_handler.backoff_strategies if self.error_handler else None
        self._http_client = HttpClient(error_handler=self.error_handler, backoff_strategy=backoff, ...)
    def send_request(self, path=None, request_params=None, request_headers=None, request_body_json=None, ...):
        url = urljoin(self._url_base.eval(config), path or self._path.eval(config, **interp_ctx))
        return self._http_client.send_request("GET"/method, url, params=request_params, headers=..., json=...)
```

### DefaultPaginator (`paginators/default_paginator.py`)

```python
class DefaultPaginator(Paginator):
    pagination_strategy: PaginationStrategy            # OffsetIncrement | PageIncrement | CursorPagination
    page_size_option:  Optional[RequestOption]         # where to put page size (query/header/body) — NOT path
    page_token_option: Optional[RequestPath|RequestOption]  # where to put the token (incl. path)
    def next_page_token(self, response, last_records, ...):
        token = self.pagination_strategy.next_page_token(response, last_records)   # None => stop
        return {"next_page_token": token} if token is not None else None
    # get_request_params/headers/body_json inject page_size + token per the *_option locations
```

### DpathExtractor (`extractors/dpath_extractor.py`)

```python
class DpathExtractor(RecordExtractor):
    field_path: List[InterpolatedString]               # e.g. ["data","items"]; [] => whole response
    decoder: Decoder = JsonDecoder()
    def extract_records(self, response):
        data = self.decoder.decode(response)
        path = [p.eval(self.config) for p in self._field_path]
        if not path: yield from (data if isinstance(data, list) else [data])
        else:
            for extracted in dpath.values(data, path):   # supports "*" wildcards
                yield from (extracted if isinstance(extracted, list) else [extracted])
```

### RecordSelector (`extractors/record_selector.py`)

```python
class RecordSelector(HttpSelector):
    extractor: RecordExtractor
    schema_normalization: TypeTransformer              # cast values to declared stream schema types
    record_filter: Optional[RecordFilter] = None       # boolean expression over the record
    transformations: List[RecordTransformation] = []   # add/remove/rename fields
    def select_records(self, response, stream_state, stream_slice, records_schema, ...):
        all_data = self.extractor.extract_records(response)
        for record in self._filter_and_transform(all_data, stream_state, stream_slice, records_schema):
            yield record   # filter -> normalize to schema -> apply transformations
```

## Data contracts

- **RequestOption:** `{ inject_into: "request_parameter"|"header"|"body_json"|"body_data", field_name }`. **RequestPath:** inject token into the URL path.
- **pagination_strategy:** `OffsetIncrement{page_size}` | `PageIncrement{page_size, start_from_page}` | `CursorPagination{cursor_value, stop_condition}` (reads next cursor from response/headers).
- **Interpolation context:** `{ config, parameters, stream_state, stream_slice, next_page_token }`.
- **Record:** `Mapping[str, Any]` after extract→filter→normalize→transform.

## Dependencies & assumptions

- Python, `dpath`, an `InterpolatedString`/Jinja interpolation layer, an `HttpClient` with retry/backoff,
  a JSON `Decoder`. Built/configured by the manifest interpreter ([[declarative-low-code-cdk--from-airbyte]]).
- Swappable: each of the four roles is an interface — add a new paginator strategy or extractor without touching the loop.

## To port this, you need:

- [ ] A retriever loop: send page → extract+select records → compute next token → stop on `None`.
- [ ] A requester with interpolated url/path/params/headers and pluggable error-handler/backoff.
- [ ] A paginator splitting *how to compute the token* (strategy) from *where to inject it* (option/path).
- [ ] An extractor with a (possibly wildcarded) JSON `field_path`; `[]` = whole response.
- [ ] A selector: filter → cast-to-schema → transformations, kept separate from extraction.
- [ ] Interpolation against config/params/state/slice/token everywhere.

## Gotchas

- **Stop on a `None` token**, not on an empty page — many APIs return a final non-empty page with no next cursor.
- **page_size can't go in the path** (only the token can) — that's why size and token are separate options.
- **`field_path: []` means whole response** — forgetting this breaks bare-array APIs.
- **Normalize to schema in the selector**, not the extractor — same extractor, different stream schemas.
- **Interpolation context must include `next_page_token` and `stream_slice`** or cursor pagination and incremental slicing can't build their URLs.
- **Backoff belongs to the error handler on the requester** — keep retry policy declarative.

## Origin (reference only)

`airbytehq/airbyte-python-cdk` @ `main`:
`airbyte_cdk/sources/declarative/retrievers/simple_retriever.py` (loop — inlined),
`.../requesters/http_requester.py`, `.../requesters/paginators/default_paginator.py`,
`.../extractors/dpath_extractor.py`, `.../extractors/record_selector.py`,
plus `.../requesters/paginators/strategies/*`, `.../requesters/error_handlers/*`, `.../interpolation/interpolated_string.py`.

**Gaps to verify (cost-capped):** exact `send_request` signature + `HttpClient` retry semantics; full
pagination-strategy set; `RecordFilter`/`TypeTransformer` internals; `LazySimpleRetriever` differences.
