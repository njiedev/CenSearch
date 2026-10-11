"""Local-only fixtures. No dataset download and no writes to the prototype."""

import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from censearch.api import create_app
from censearch.config import ROOT, Settings


@pytest.fixture(scope="session")
def calibration():
    return json.loads((ROOT / "reports/calibration.json").read_text())


@pytest.fixture(scope="session")
def photo_folder():
    default = next(
        line.removeprefix("PHOTOS ?= ").strip()
        for line in (ROOT / "Makefile").read_text().splitlines()
        if line.startswith("PHOTOS ?= ")
    )
    folder = Path(os.environ.get("LIKENESS_TEST_PHOTOS", default))
    people = folder / "people" if (folder / "people").is_dir() else folder
    candidates = sorted(path for path in people.glob("*/reference") if path.is_dir())
    if not candidates:
        pytest.fail("Set LIKENESS_TEST_PHOTOS to a local <person>/reference, originals, wild photo folder")
    return candidates[0].parent


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for key in ("SERPAPI_API_KEY", "OPENAI_API_KEY", "OBJ_ENDPOINT", "OBJ_BUCKET", "OBJ_ACCESS_KEY", "OBJ_SECRET_KEY"):
        monkeypatch.setenv(key, "")
    return Settings(
        _env_file=None,
        LIKENESS_DATA_DIR=tmp_path,
        LIKENESS_MODELS_DIR=ROOT / "models",
        allow_public_crawl=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as value:
        yield value


@pytest.fixture
def enrolled(client, photo_folder):
    reference = sorted((photo_folder / "reference").glob("*.jpg"))[0]
    original = sorted((photo_folder / "originals").glob("*.jpg"))[0]
    response = client.post(
        "/api/people",
        data={
            "name": "Local fixture",
            "consent": "Local test fixture only",
            "ownership": "Hypothetical fixture ownership for local testing",
            "development_fixture": "true",
        },
        files=[
            ("references", (reference.name, reference.read_bytes(), "image/jpeg")),
            ("originals", (original.name, original.read_bytes(), "image/jpeg")),
        ],
    )
    assert response.status_code == 201, response.text
    return response.json()["person"]
