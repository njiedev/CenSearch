FROM node:24.14.1-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/
RUN npm ci
COPY frontend/ frontend/
RUN VITE_BACKEND=1 npm run build

FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
# The image ships 3.12 at a different patch level than .python-version pins, so name it outright.
ENV UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/bin/python3.12 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
COPY backend/censearch/ censearch/
COPY backend/mockweb/ mockweb/
RUN uv sync --frozen --no-dev
COPY backend/reports/calibration.json reports/calibration.json
COPY backend/scripts/setup_models.py scripts/setup_models.py
RUN uv run --no-sync python scripts/setup_models.py
COPY --from=frontend /build/frontend/dist /frontend/dist
ENV LIKENESS_DATA_DIR=/app/data LIKENESS_FRONTEND_DIR=/frontend/dist
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "censearch.api:app", "--host", "127.0.0.1", "--port", "8000"]
