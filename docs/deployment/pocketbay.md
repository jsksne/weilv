# PocketBay competition deployment

Release commit: `37ed2af5a7f9496adf2350e7406ca91b326e48b8`

The PocketBay deployment is one Docker-backed Web Service: the image builds the Vue production bundle, FastAPI serves it at the same HTTPS origin, and `/api/*` remains handled by FastAPI. The app binds to the platform-provided `PORT`; it does not run a Vite development server in production.

## Required PocketBay runtime secrets

- `DASHSCOPE_API_KEY`
- `ELASTICSEARCH_URL` (an externally managed Elasticsearch 8.x endpoint)
- One Elasticsearch authentication method: `ELASTICSEARCH_API_KEY`, or both `ELASTICSEARCH_USERNAME` and `ELASTICSEARCH_PASSWORD`
- `WEILV_ELASTICSEARCH_SERVERLESS=1` when the selected Elastic Cloud deployment is Serverless

TLS certificate verification stays enabled by default. Set `ELASTICSEARCH_CA_CERTS` only when the managed service requires a custom CA file; do not disable verification in production. Do not put secret values in source, Docker build arguments, or the Vue bundle.

PocketBay does not provide Elasticsearch. Use an externally managed Elasticsearch 8.x-compatible service with private credentials and outbound access from PocketBay. The source data is external/unmanaged, so this release can run normally but is not configured as a platform-licensed copy.

## Initial deployment and bootstrap

Build arguments are intentionally non-secret: `VITE_UI_MODE=production`, `VITE_USER_ID=competition-demo-user`, and `VITE_API_BASE_URL=/`.

For the initial release only, set `WEILV_BOOTSTRAP_ON_START=1`. The image then runs the committed `bootstrap_micro_tasks.py` and `bootstrap_health_knowledge.py` before Uvicorn starts, creating the seven indices and loading 23 micro tasks plus 29 reviewed knowledge chunks. Disable this flag after bootstrap to avoid re-embedding data on later restarts or redeployments.

Before deploying to Elastic Cloud Serverless, set `WEILV_ELASTICSEARCH_SERVERLESS=1` and run `python scripts/probe_elasticsearch_serverless.py` with the same runtime environment. The probe creates, maps, indexes, gets, and deletes one timestamped temporary index; it does not bootstrap production data.

Use `/health` for the PocketBay health check. It is a local FastAPI response and does not call DashScope. Dynamic services may cold-start after PocketBay idle sleep; before a demo, visit `/health` and then open the homepage.

## Validation

After PocketBay reports `running`, verify HTTPS, production mode, fixture fallback `0`, onboarding with Memory off, B1/B2/B4/B5/B6, the NDJSON B3 stream, assistant sources, and safety behavior. `USER_IDENTITY_SEAM` is intentionally a controlled competition identity, not an authentication system. Weekly aggregation uses the existing UTC day boundary.

The raw third-party source document for SRC-001 is not redistributed. The release includes its provenance metadata; full source-line verification remains optional through `WEILV_SOURCE_DOCUMENTS_DIR` in a lawful local environment.
