#!/usr/bin/env bash
# Build an allowlisted source archive without photos, credentials or runtime data.
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
bundle=${1:?Pass the output archive path}
COPYFILE_DISABLE=1 tar --format=ustar --exclude='__pycache__' --exclude='*.pyc' --exclude='node_modules' --exclude='dist' --exclude='*.md' --exclude='frontend/public/photos' \
    -czf "$bundle" -C "$repo_root" .dockerignore \
    backend/pyproject.toml backend/uv.lock backend/.python-version \
    backend/censearch backend/mockweb backend/scripts/setup_models.py \
    backend/reports/calibration.json backend/demo-ui backend/deploy \
    frontend/package.json frontend/package-lock.json frontend/index.html frontend/signup.html \
    frontend/matches.html frontend/app frontend/contact frontend/legal frontend/public \
    frontend/src frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json frontend/vite.config.ts
