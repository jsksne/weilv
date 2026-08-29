FROM node:24-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_USER_ID
ARG VITE_API_BASE_URL=/
ENV VITE_UI_MODE=production \
    VITE_USER_ID=${VITE_USER_ID} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN test -n "$VITE_USER_ID" && test -n "$VITE_API_BASE_URL"
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.0 AS uv

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src
WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY docker-entrypoint.sh /usr/local/bin/weilv-start
RUN sed -i 's/\r$//' /usr/local/bin/weilv-start && chmod 755 /usr/local/bin/weilv-start

ENTRYPOINT ["/usr/local/bin/weilv-start"]
