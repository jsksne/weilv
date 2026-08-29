# PocketBay Production Deployment

The supported production shape is one Docker Web Service. The image builds the
Vue bundle with `VITE_UI_MODE=production`, then FastAPI serves that bundle and
the `/api/*` routes from the same HTTPS origin. This keeps the browser API base
URL as `/` and avoids a development server or fixture data in the deployed app.

## Build settings

Set these non-secret Docker build arguments in the existing PocketBay project:

```text
VITE_USER_ID=<controlled-production-user-id>
VITE_API_BASE_URL=/
```

`VITE_UI_MODE` is fixed to `production` by the Dockerfile. The user id is the
current identity integration seam, not an authentication system; use the
existing controlled production identity for this project.

## Runtime settings

Set these as PocketBay runtime secrets/environment variables. Do not put them
in Docker build arguments or the Vue bundle:

```text
DASHSCOPE_API_KEY=<secret>
ELASTICSEARCH_URL=https://<managed-elasticsearch-host>
ELASTICSEARCH_API_KEY=<secret>
```

Use `ELASTICSEARCH_USERNAME` and `ELASTICSEARCH_PASSWORD` instead of the API
key when that is the selected authentication method. Keep certificate
verification enabled; set `ELASTICSEARCH_CA_CERTS` only when the service needs
a custom CA. Set `WEILV_ELASTICSEARCH_SERVERLESS=1` for Elastic Serverless.

For a separately hosted frontend, set the backend process environment
`WEILV_CORS_ORIGINS=https://<frontend-origin>` and build the frontend with
`VITE_API_BASE_URL=https://<backend-origin>`. Never use `localhost` in a
browser build that users will access remotely.

## First data bootstrap

For the first deployment only, set `WEILV_BOOTSTRAP_ON_START=1`. The entrypoint
uses the same configured Elasticsearch authentication as the API and loads the
reviewed `micro_tasks_v1` and `health_knowledge_v1` data using real DashScope
embeddings. Turn the variable off after the indices contain the data so a
restart does not repeat paid embedding calls.

The existing project previously used a bootstrap-on runtime setting. After the
existing indices are confirmed populated, save `WEILV_BOOTSTRAP_ON_START=0`
before or during this redeploy.

## Verification

The service health check is `GET /health`. The Agentic assistant endpoint used
by the production UI is `POST /api/v1/recommend/agentic/stream`; its completed
event carries the final answer from that same run and only the allowlisted
public RAG factors/excerpts. Internal diagnostics, prompts, scores, embeddings,
and memory contents are not sent in the stream.

After PocketBay reports `running`, verify the HTTPS homepage, the Today Hero,
progress row, and Observation card; then submit a non-template question in
“问问薇薇” and confirm the returned sources are from the real knowledge index.
The page must not show a Demo badge.

No new PocketBay project or service is required; redeploy the existing
`weilv-competition` project.
