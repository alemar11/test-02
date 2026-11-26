# test-02

`test-02` is the client repository for the cross-repository test environment.
It contains a Python client and a small CLI that consume the static GET API
provided by [`test-01`](https://github.com/alemar11/test-01).

There is intentionally no UI, database, or write operation. This repository
represents the consumer side of the API contract and is the place to develop
client-facing behavior and cross-repository integration tests.

Start the API in `test-01`, then run one of these commands:

```bash
uv run test-02 health
uv run test-02 --timeout 2.5 items
uv run test-02 capabilities
uv run test-02 item item-1
uv run test-02 vocabulary
uv run test-02 items
uv run test-02 items --label featured --status active --sort name --limit 5
uv run test-02 batch item-2 missing item-1
uv run test-02 facets --label read-only --status active
uv run test-02 summary
uv run test-02 summary --status active --label support --q " SECOND "
```

Use global `--base-url` and `--timeout` options before the command to point the
client at another local API instance and set a finite, positive request timeout
in seconds. The default timeout is `5.0`; invalid timeout values are rejected
by the argument parser before the client or network is used. The `items`
command supports `--status`, `--category`, `--label`, `--q`, `--sort`,
`--order`, `--page`, and `--limit`. Supported sort values are `id`, `name`,
`status`, and, when advertised by the provider, `category`. It prints
deterministic, sorted-key JSON with the complete discovery envelope:

```json
{
  "data": [
    {
      "category": "core-service",
      "id": "item-1",
      "labels": [
        "featured",
        "read-only"
      ],
      "name": "First item",
      "status": "active"
    }
  ],
  "pagination": {
    "limit": 5,
    "page": 1,
    "total": 1,
    "totalPages": 1
  },
  "query": {
    "category": null,
    "label": "featured",
    "limit": 5,
    "order": "asc",
    "page": 1,
    "q": null,
    "sort": "name",
    "status": "active"
  }
}
```

Python callers can choose between the validated discovery envelope and the
existing data-only convenience method:

```python
from test_02.client import ApiClient

client = ApiClient("http://127.0.0.1:3000", timeout=2.5)
manifest = client.capabilities()
envelope = client.discover_items(label="featured", sort="name", limit=5)
items = client.list_items()
batch = client.get_items(["item-2", "missing", "item-1"])
facets = client.item_facets(label="read-only", status="active")
summary = client.item_summary(label="support", status="active", q=" second ")
vocabulary = client.item_vocabulary()
```

`discover_items()` validates options locally before sending a request. Blank
filters, unsupported sorting, an order without a sort, pages outside 1 through
JavaScript's maximum safe integer (`9007199254740991`), and limits outside 1
through 100 raise `ApiError`. Transport failures, HTTP errors, invalid JSON, and
malformed collection envelopes also have distinct `ApiError` messages.
`list_items()` intentionally keeps the original unqueried
`{ "data": [...] }` response compatibility and returns only the data array.
Category sorting uses the provider's ordinal comparison, defaults to ascending
order, and uses ascending item ID as the tie-breaker in either direction.

## Item details

The `item` command and `ApiClient.get_item()` read one exact item ID from
`GET /api/items/{id}`:

```bash
uv run test-02 item item-1
```

```python
from test_02.client import ApiClient

client = ApiClient("http://127.0.0.1:3000")
item = client.get_item("item-1")
```

The client validates the returned `data` object, including its exact `id`,
string `name`, `status`, and `category`, and its list of string `labels`.
Input IDs must be non-blank strings. IDs are percent-encoded as one URL path
segment, so reserved characters cannot add a query or fragment. Unknown IDs
retain the API's HTTP 404 error and the CLI's stderr-only exit status `1`.

## Capability discovery

The fixed `capabilities` command and `ApiClient.capabilities()` read
`GET /api/capabilities` on every invocation. They accept provider schema
version `1` only and validate the unique capability identities plus the
required consumer contract for health, item collection, item facets, and
item summaries, and capability discovery. Required methods, paths, filter
behavior, sorting, normalization, defaults, pagination range, and result limit
must remain compatible. The optional `item-vocabulary` capability is validated
when advertised, while older manifests without it remain compatible.

Compatibility is subset-based: new capability IDs and fields are preserved in
the returned manifest and printed output. The `item-batch` capability is
additive, so older manifests remain valid; when present, its path and scalar
`ids` bounds are validated. Missing or duplicate identities, malformed entries,
incompatible required semantics, unsupported schemas, transport or HTTP
failures, and invalid JSON fail closed with `ApiError`.
Discovery is never inferred from another endpoint and has no cache or stale
fallback. The CLI prints sorted-key JSON on success; failures print only the
established `error: ...` stderr line and exit with status `1`.

## Item vocabulary

The `vocabulary` command and `ApiClient.item_vocabulary()` request the complete
provider-owned set of status, category, and label values without downloading
the item collection:

```bash
uv run test-02 vocabulary
```

The client preserves and returns the complete response envelope:

```json
{
  "data": {
    "categories": ["core-service", "support-service"],
    "labels": ["featured", "read-only", "support"],
    "statuses": ["active"]
  }
}
```

Each array may be empty, but every value must be a non-blank string. Values
must be unique and sorted with JavaScript's ordinal UTF-16 ordering, matching
the provider's deterministic `Array.sort()` contract. Malformed, duplicate, or
unordered arrays fail with `ApiError`; the CLI reports the established
`error: ...` message and exits with status `1`.

## Offline environment diagnostics

Inspect client configuration, Python compatibility, and installed package
identity without contacting an API:

```bash
uv run test-02-diagnostics
uv run test-02-diagnostics --base-url https://api.example.test/ --timeout 2.5
```

The command prints deterministic JSON and exits with status `0` when every
diagnostic passes. Malformed URLs, non-finite or non-positive timeouts, an
unsupported Python runtime, or unavailable package metadata are reported in
the JSON and produce exit status `1`. This command is independent from the
live `test-02 health` and `test-02 items` commands and never makes a network
request.

## Ordered batch reads

The `batch` command and `ApiClient.get_items()` read several exact item IDs in
one request. IDs must be a non-empty list of 1–50 unique strings matching
`[A-Za-z0-9_-]+`. The client sends them as the single scalar `ids` query value
and validates that found items and missing IDs are disjoint, complete, and in
the same order as the request.

Run a mixed batch, including an unknown ID:

```bash
uv run test-02 batch item-2 missing item-1
```

The command prints the complete sorted-key response envelope:

```json
{
  "data": [
    {
      "id": "item-2",
      "name": "Second item"
    },
    {
      "id": "item-1",
      "name": "First item"
    }
  ],
  "missing": [
    "missing"
  ]
}
```

Python callers use the same validated operation:

```python
from test_02.client import ApiClient

client = ApiClient("http://127.0.0.1:3000")
batch = client.get_items(["item-2", "missing", "item-1"])
```

Malformed input is rejected before HTTP. Malformed or inconsistent partitions,
transport failures, HTTP errors, invalid JSON, and non-object responses raise
`ApiError`; the CLI reports those failures on stderr using the established
`error: ...` format and exits with status `1`.

## Item summaries

The `summary` command and `ApiClient.item_summary()` request provider-owned
aggregates over the complete matching item set. They support only `status`,
`category`, `label`, and `q`; sorting, ordering, and pagination are intentionally
excluded. Status, category, and label retain exact matching semantics. The
client sends the original non-blank `q` value and verifies the provider's
trimmed, case-normalized filter echo.

Run the command without filters or with any supported filter combination:

```bash
uv run test-02 summary
uv run test-02 summary --status active --category support-service --label support --q " SECOND "
```

Python callers use the same validated operation:

```python
from test_02.client import ApiClient

client = ApiClient("http://127.0.0.1:3000")
summary = client.item_summary(
    status="active",
    label="support",
    q=" SECOND ",
)
```

returns the validated provider envelope:

```json
{
  "data": {
    "byCategory": {
      "support-service": 1
    },
    "byStatus": {
      "active": 1
    },
    "total": 1
  },
  "insights": {
    "byStatus": {
      "active": 1
    },
    "filters": {
      "category": null,
      "label": "support",
      "q": "second",
      "status": "active"
    },
    "matching": 1,
    "total": 2
  }
}
```

The client validates every required summary and insight field, non-negative
integer counts, status and category grouping totals, matching versus global
totals, matching status insights, and the echoed filters. Required fields are
subset-checked so additive provider metadata remains compatible. Empty filtered
sets are valid when matching totals are zero and grouping maps are empty. Blank
or non-string filters fail before a request; transport, HTTP, invalid-JSON,
top-level-shape, and summary-shape errors remain distinct `ApiError` failures.
The client consumes these aggregates directly and never recounts downloaded
items.

## Complete item iteration

`ApiClient.iter_items()` lazily yields every item in the matching catalog result:

```python
for item in client.iter_items(
    status="active",
    sort="name",
    page_size=100,
    max_pages=1000,
):
    print(item["id"], item["name"])
```

The iterator accepts the same status, category, label, query, sort, and order
filters as `discover_items()`. `page_size` must be an integer from 1 through
100 and defaults to 100. `max_pages` must be positive and defaults to 1000.
No request is made until the iterator is advanced. It requests page 1 first,
including for an empty result, then fetches one subsequent page at a time.

Each page is validated with `discover_items()` before any item from that page
is yielded. The iterator also requires the reported total and page count to
remain stable and every item ID to be a non-blank unique string across the
whole iteration. If a later page fails validation or transport, earlier items
may already have been yielded; callers that need all-or-nothing output should
buffer the iterator before writing results.

## CSV export

The `export` command writes the complete matching catalog to standard output:

```bash
uv run test-02 export --sort name --order asc --page-size 100 --max-pages 1000
```

It supports the same status, category, label, query, sort, and order filters as
`items`, plus `--page-size` (1 through 100, default 100) and `--max-pages`
(positive integer, default 1000). The CSV columns are `id`, `name`, `status`,
`category`, and `labels`; labels is a compact JSON array in the provider's
order. Standard-library CSV quoting preserves commas, quotes, and newlines in
source values. The complete iterator is consumed before the header or any row
is written, so a later-page or malformed-record failure leaves stdout empty and
uses the existing `error: ...` stderr response. Empty results write the header
only.

## Facet insights

The `facets` command and `ApiClient.item_facets()` request server-owned label
counts over the complete matching item set. They support only `status`,
`category`, `label`, and `q`; pagination and sorting are intentionally not
facet controls. Exact filters are preserved, while `q` is trimmed and
case-normalized by the provider and verified by the client.

For example:

```bash
uv run test-02 facets --status active --q " ITEM "
```

prints sorted-key JSON with the complete facet envelope:

```json
{
  "data": {
    "byCategory": {
      "core-service": 1,
      "support-service": 1
    },
    "byLabel": {
      "featured": 1,
      "read-only": 2,
      "support": 1
    },
    "total": 2
  },
  "filters": {
    "category": null,
    "label": null,
    "q": "item",
    "status": "active"
  }
}
```

Each matching item contributes to every label it carries, so the sum of label
counts can be greater than `data.total`. The provider may also include
`byCategory`; when present, it contains non-blank category names with strictly
positive integer counts whose sum is exactly `data.total`. A category-filtered
result with matches contains exactly the requested category and its total.
Legacy label-only responses without `byCategory` remain valid, and unknown
additive fields are preserved in the returned envelope and CLI output. A query
with no matches returns `total: 0` and empty `byLabel` and `byCategory` objects
when the provider supplies both. Blank or non-string client filters fail
locally before a request. Transport, HTTP, invalid-JSON, top-level shape,
facet-data, and normalized-filter mismatches remain distinct `ApiError` failures
and use the CLI's established `error: ...` stderr contract.

## Cross-repository contract

Capability discovery is validated against the published provider contract from
[provider PR #68](https://github.com/alemar11/test-01/pull/68), exact candidate
`a42ae787504f161f7dd69b4d0c48afe9a4b14e4a`. The provider checkout is contract
evidence only and never Git ancestry for this repository.

To reproduce the live read-only check, prepare an isolated `test-01` checkout
with its dependencies, then pin and verify it before starting the API:

```bash
provider_worktree=/absolute/path/to/test-01-provider-candidate
test "$(git -C "$provider_worktree" rev-parse HEAD)" = \
  a42ae787504f161f7dd69b4d0c48afe9a4b14e4a
test -z "$(git -C "$provider_worktree" status --porcelain)"
npm --prefix "$provider_worktree" start
```

From this consumer repository in another shell, run:

```bash
uv run test-02 --base-url http://127.0.0.1:3000 capabilities
```

The command must exit `0` with deterministic sorted-key schema version 1 JSON.
After stopping the server, repeat the provider SHA and cleanliness checks to
confirm that verification did not change provider state.

The ordered batch contract is checked against the pinned `test-01` provider
candidate `d63d09b81dc85b5f6b94327b0fbadaa2d08b3bc6` on
`codex/catalog-batch-provider`. It advertises the additive `item-batch`
capability and serves `GET /api/items/batch?ids=item-2,missing,item-1` with
found items and missing IDs in their requested order. The consumer validates
this response over loopback without sharing Git history with or modifying the
provider repository.

To reproduce the batch contract in an isolated provider checkout:

```bash
provider_worktree="$(mktemp -d)"
git clone https://github.com/alemar11/test-01.git "$provider_worktree"
git -C "$provider_worktree" fetch origin codex/catalog-batch-provider
git -C "$provider_worktree" checkout --detach d63d09b81dc85b5f6b94327b0fbadaa2d08b3bc6
test -z "$(git -C "$provider_worktree" status --porcelain)"
cd "$provider_worktree"
npm ci
npm start
```

Then run the consumer against that server:

```bash
uv run test-02 --base-url http://127.0.0.1:3000 batch item-2 missing item-1
```

The result must contain `item-2` and `item-1` in `data`, and `missing` in the
`missing` array. Stop the server and repeat the provider SHA and cleanliness
checks after the read-only integration test.

The item-summary client contract is also checked against `test-01` `main` at
[provider commit
`19179395350920916f348485dab8d70bd000780c`](https://github.com/alemar11/test-01/commit/19179395350920916f348485dab8d70bd000780c).
That provider advertises schema-version-1 `item-summary` compatibility and
serves the complete `data` plus `insights` envelope documented above. The
network-free client tests exercise full, filtered, empty, additive, malformed,
and cross-field-inconsistent responses without changing provider state.

The discovery shape remains tested against the label-aware `test-01` contract from
[provider PR #60](https://github.com/alemar11/test-01/pull/60), verified at
candidate `73d294e027f99e0017d971410dd05c5f67561e55`. That provider accepts scalar
`status`, `category`, `label`, `q`, `sort`, `order`, `page`, and `limit`
controls. Queried reads return exactly `data`, `pagination`, and the normalized
eight-field `query` metadata object. This repository consumes that contract
without sharing Git history with or modifying `test-01`.

Category sorting is tested against the provider candidate at commit
[`71851f2d600fb4b14c42329a7ff15ac113445c72`](https://github.com/alemar11/test-01/commit/71851f2d600fb4b14c42329a7ff15ac113445c72).
The provider advertises `category` as an additive collection sort value while
retaining the existing `id`, `name`, and `status` values. Older capability
manifests remain readable; the consumer enables category sorting when the
provider advertises it.

To reproduce the pinned category-sorting loopback check:

```bash
git clone https://github.com/alemar11/test-01.git /tmp/test-01-category-sort-contract
git -C /tmp/test-01-category-sort-contract checkout --detach 71851f2d600fb4b14c42329a7ff15ac113445c72
npm --prefix /tmp/test-01-category-sort-contract ci
npm --prefix /tmp/test-01-category-sort-contract start
```

Then run `uv run test-02 --base-url http://127.0.0.1:3000 capabilities` and
`uv run test-02 --base-url http://127.0.0.1:3000 items --sort category --order desc`
from this repository. The result must preserve the full discovery envelope,
category ordering, ID tie-breaker, filters, and pagination metadata.

The facet tests mirror the separate provider contract from
[provider PR #61](https://github.com/alemar11/test-01/pull/61), verified at
candidate `77591b055d4ea68237f7b83978ebc144768fb3a5`. Its
`GET /api/items/facets` response has exactly `data` and `filters`; `data` has
`total` and `byLabel`; and `filters` records the exact `status`, `category`,
and `label` values plus normalized `q`. The repositories stay independent:
the provider candidate is contract evidence, never Git ancestry for test-02.

The facet tests mirror the `test-01` main contract at provider commit
[`e969a59969d7a673fff8874ab5d1160b81c5546d`](https://github.com/alemar11/test-01/commit/e969a59969d7a673fff8874ab5d1160b81c5546d).
Its `GET /api/items/facets` response requires `data.total` and `data.byLabel`,
and may include `data.byCategory`; the optional category map partitions the
matching total. `filters` records the exact `status`, `category`, and `label`
values plus normalized `q`. The repositories stay independent: the provider
candidate is contract evidence, never Git ancestry for test-02.

To reproduce the live facet contract in an isolated provider checkout:

```bash
provider_worktree=$(mktemp -d /tmp/test-01-facet-contract.XXXXXX)
git clone https://github.com/alemar11/test-01.git "$provider_worktree"
git -C "$provider_worktree" checkout --detach \
  e969a59969d7a673fff8874ab5d1160b81c5546d
test "$(git -C "$provider_worktree" rev-parse HEAD)" = \
  e969a59969d7a673fff8874ab5d1160b81c5546d
test -z "$(git -C "$provider_worktree" status --porcelain)"
(cd "$provider_worktree" && npm ci)
provider_port=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
printf 'provider_port=%s\n' "$provider_port"
(cd "$provider_worktree" && PORT="$provider_port" npm start) &
provider_pid=$!
trap 'kill "$provider_pid"; wait "$provider_pid" 2>/dev/null || true' EXIT
```

Then, from this repository in another shell, set `provider_port` to the port
printed by the first shell and run the consumer against it:

```bash
uv run test-02 --base-url "http://127.0.0.1:$provider_port" facets --status active --q " ITEM "
```

The command must produce the deterministic envelope shown above, including
`byCategory`. After stopping the server, repeat the provider SHA and
cleanliness checks to confirm that verification did not change provider state.
The unit tests exercise the same exact response keys, optional category map,
legacy label-only response, filter normalization, empty-map, multi-label,
unsupported-control, and error contracts without contacting or changing
`test-01`.

The vocabulary contract is tested against the provider candidate at commit
[`e22285c39b8748aab84ff5eb691f4853c8a38c19`](https://github.com/alemar11/test-01/commit/e22285c39b8748aab84ff5eb691f4853c8a38c19).
That candidate advertises the optional `item-vocabulary` capability and serves
the exact `{ "data": { "statuses": [], "categories": [], "labels": [] } }`
envelope. To reproduce the pinned loopback check:

```bash
git clone https://github.com/alemar11/test-01.git /tmp/test-01-vocabulary-contract
git -C /tmp/test-01-vocabulary-contract checkout --detach e22285c39b8748aab84ff5eb691f4853c8a38c19
npm --prefix /tmp/test-01-vocabulary-contract ci
npm --prefix /tmp/test-01-vocabulary-contract start
```

Then run `uv run test-02 --base-url http://127.0.0.1:3000 capabilities` and
`uv run test-02 --base-url http://127.0.0.1:3000 vocabulary` from this
repository. The vocabulary arrays must remain unique, non-blank, and in
JavaScript ordinal order; the provider must reject any vocabulary query.

Run the tests and syntax check with:

```bash
uv run python -m unittest discover -s tests
uv run python -m compileall -q src tests
```

## Dummy-project coordination probe

Run the opt-in skill-validation probe against a supplied provider base URL:

```sh
uv run test-02 --base-url http://127.0.0.1:3000 coordination-probe
```

The command sends `GET /api/coordination-probe` and prints the JSON object only
when `protocol` is `"se-coordination-v2"` and `revision` is the integer `1`.
It exits with status 1 and an error on stderr for an incompatible contract,
network/HTTP failure, invalid JSON, or a non-object response. Boolean, string,
and floating-point revisions are rejected. This dummy-project skill-validation
command is separate from the older smoke tests and runs only when requested.
