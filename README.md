# test-02

`test-02` is the client repository for the cross-repository test environment.
It contains a Python client and a small CLI that consume the static GET API
provided by `test-01`.

There is intentionally no UI, database, or write operation. This repository
represents the consumer side of the API contract and is the place to develop
client-facing behavior and cross-repository integration tests.

Start the API in `test-01`, then run one of these commands:

```bash
uv run test-02 health
uv run test-02 capabilities
uv run test-02 items
uv run test-02 items --label featured --status active --sort name --limit 5
uv run test-02 facets --label read-only --status active
uv run test-02 summary
uv run test-02 summary --status active --label support --q " SECOND "
```

Use `--base-url` before the command to point the client at another local API
instance. The `items` command supports `--status`, `--category`, `--label`,
`--q`, `--sort`, `--order`, `--page`, and `--limit`. It prints deterministic,
sorted-key JSON with the complete discovery envelope:

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

client = ApiClient("http://127.0.0.1:3000")
manifest = client.capabilities()
envelope = client.discover_items(label="featured", sort="name", limit=5)
items = client.list_items()
facets = client.item_facets(label="read-only", status="active")
summary = client.item_summary(label="support", status="active", q=" second ")
```

`discover_items()` validates options locally before sending a request. Blank
filters, unsupported sorting, an order without a sort, pages outside 1 through
JavaScript's maximum safe integer (`9007199254740991`), and limits outside 1
through 100 raise `ApiError`. Transport failures, HTTP errors, invalid JSON, and
malformed collection envelopes also have distinct `ApiError` messages.
`list_items()` intentionally keeps the original unqueried
`{ "data": [...] }` response compatibility and returns only the data array.

## Capability discovery

The fixed `capabilities` command and `ApiClient.capabilities()` read
`GET /api/capabilities` on every invocation. They accept provider schema
version `1` only and validate the unique capability identities plus the
required consumer contract for health, item collection, item facets, and
item summaries, and capability discovery. Required methods, paths, filter
behavior, sorting, normalization, defaults, pagination range, and result limit
must remain compatible.

Compatibility is subset-based: new capability IDs and fields are preserved in
the returned manifest and printed output. Missing or duplicate identities,
malformed entries, incompatible required semantics, unsupported schemas,
transport or HTTP failures, and invalid JSON fail closed with `ApiError`.
Discovery is never inferred from another endpoint and has no cache or stale
fallback. The CLI prints sorted-key JSON on success; failures print only the
established `error: ...` stderr line and exit with status `1`.

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
counts can be greater than `data.total`. A query with no matches returns
`total: 0` and an empty `byLabel` object. Blank or non-string client filters
fail locally before a request. Transport, HTTP, invalid-JSON, top-level shape,
facet-data, and normalized-filter mismatches remain distinct `ApiError`
failures and use the CLI's established `error: ...` stderr contract.

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

The facet tests mirror the separate provider contract from
[provider PR #61](https://github.com/alemar11/test-01/pull/61), verified at
candidate `77591b055d4ea68237f7b83978ebc144768fb3a5`. Its
`GET /api/items/facets` response has exactly `data` and `filters`; `data` has
`total` and `byLabel`; and `filters` records the exact `status`, `category`,
and `label` values plus normalized `q`. The repositories stay independent:
the provider candidate is contract evidence, never Git ancestry for test-02.

To reproduce the live facet contract in an isolated provider checkout:

```bash
git clone https://github.com/alemar11/test-01.git /tmp/test-01-facet-contract
git -C /tmp/test-01-facet-contract fetch origin pull/61/head
git -C /tmp/test-01-facet-contract checkout --detach 77591b055d4ea68237f7b83978ebc144768fb3a5
npm --prefix /tmp/test-01-facet-contract ci
npm --prefix /tmp/test-01-facet-contract start
```

Then, from this repository in another shell, run the consumer against it:

```bash
uv run test-02 --base-url http://127.0.0.1:3000 facets --status active --q " ITEM "
```

The command must produce the deterministic envelope shown above. The unit
tests exercise the same exact response keys, filter normalization, empty-map,
multi-label, unsupported-control, and error contracts without contacting or
changing test-01.

Run the tests and syntax check with:

```bash
uv run python -m unittest discover -s tests
uv run python -m compileall -q src tests
```
