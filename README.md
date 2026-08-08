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
```

Use `--base-url` to point the client at another local API instance. Run the
client tests with `uv run python -m unittest discover -s tests`.

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
