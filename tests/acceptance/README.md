# Acceptance tests

These tests run against a live API instance and require real credentials.

Set these environment variables before running:
- `HAWK_API_KEY` — a valid test or live API key
- `HAWK_API_BASE_URL` — the API base URL (default: `http://localhost:8090`)

Run:
```bash
HAWK_API_KEY=hawk_test_xxx HAWK_API_BASE_URL=http://localhost:8090 pytest tests/acceptance/ -v -s
```

These tests are excluded from the standard test suite because they require a running API server, live Redis, PostgreSQL, and a valid DeepL key. Do not run them in CI without those dependencies.
