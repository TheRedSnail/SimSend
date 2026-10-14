# ---- Stage 1: build the frontend ----
FROM node:20-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime (backend serves the API and the built frontend) ----
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH" \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5001 \
    FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app/backend

# Dependencies first for layer caching
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN useradd --create-home --uid 1000 app \
  && mkdir -p uploads logs \
  && chown -R app:app uploads logs
USER app

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"FLASK_PORT\", \"5001\")}/health', timeout=4)"

# waitress, serving the API and the built frontend (see backend/wsgi.py)
CMD ["python", "wsgi.py"]
