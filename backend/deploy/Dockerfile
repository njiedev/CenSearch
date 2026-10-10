FROM node:24.14.1-bookworm-slim AS console
WORKDIR /console
COPY demo-ui/package.json demo-ui/package-lock.json ./
RUN npm ci
COPY demo-ui/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY censearch/ censearch/
COPY mockweb/ mockweb/
RUN uv sync --frozen --no-dev --python /usr/bin/python3.12
COPY reports/calibration.json reports/calibration.json
COPY scripts/setup_models.py scripts/setup_models.py
RUN uv run python scripts/setup_models.py
COPY --from=console /console/dist demo-ui/dist
ENV LIKENESS_DATA_DIR=/app/data
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "censearch.api:app", "--host", "127.0.0.1", "--port", "8000"]
