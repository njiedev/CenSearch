PHOTOS ?= seed
API_PORT ?= 8490
BASE_PORT ?= 9111

.PHONY: setup test api mock seed e2e e2e-round2 e2e-round3 e2e-app

setup:
	uv sync --frozen
	uv run python scripts/setup_models.py $(if $(MODEL_SOURCE),--source "$(MODEL_SOURCE)",)
	uv run playwright install chromium
	cd .. && npm ci && VITE_BACKEND=1 npm run build

test:
	uv run pytest

api:
	uv run uvicorn censearch.api:app --host 127.0.0.1 --port 8190 --reload --reload-dir censearch

seed:
	uv run python -m mockweb.seed --photos "$(PHOTOS)" --output "$(MOCK_ROOT)"

mock:
	uv run python -m mockweb.run --root "$(MOCK_ROOT)"

e2e:
	uv run python scripts/e2e.py --photos "$(PHOTOS)" --api-port $(API_PORT) --base-port $(BASE_PORT)

e2e-round2:
	uv run python scripts/e2e_round2.py --photos "$(PHOTOS)" --api-port $(API_PORT) --base-port $(BASE_PORT)

e2e-round3:
	uv run python scripts/e2e_round3.py --photos "$(PHOTOS)" --api-port $(API_PORT) --base-port $(BASE_PORT)

e2e-app:
	uv run python scripts/e2e_app.py --photos "$(PHOTOS)" --api-port $(API_PORT) --base-port $(BASE_PORT)
