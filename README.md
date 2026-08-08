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
uv run test-02 items
uv run test-02 items --label featured --status active --sort name --limit 5
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
envelope = client.discover_items(label="featured", sort="name", limit=5)
items = client.list_items()
```

`discover_items()` validates options locally before sending a request. Blank
filters, unsupported sorting, an order without a sort, pages outside 1 through
JavaScript's maximum safe integer (`9007199254740991`), and limits outside 1
through 100 raise `ApiError`. Transport failures, HTTP errors, invalid JSON, and
malformed collection envelopes also have distinct `ApiError` messages.
`list_items()` intentionally keeps the original unqueried
`{ "data": [...] }` response compatibility and returns only the data array.

## Cross-repository contract

The discovery shape is tested against the label-aware `test-01` contract from
[provider PR #60](https://github.com/alemar11/test-01/pull/60), verified at
candidate `73d294e027f99e0017d971410dd05c5f67561e55`. That provider accepts scalar
`status`, `category`, `label`, `q`, `sort`, `order`, `page`, and `limit`
controls. Queried reads return exactly `data`, `pagination`, and the normalized
eight-field `query` metadata object. This repository consumes that contract
without sharing Git history with or modifying `test-01`.

Run the tests and syntax check with:

```bash
uv run python -m unittest discover -s tests
uv run python -m compileall -q src tests
```
