.PHONY: install dev dev-backend dev-web test test-backend test-web build clean

install:
	pip install -r requirements.txt
	cd web && npm install

dev-backend:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd web && npm run dev

dev:
	@echo "Starting backend (8000) + web (3000) in parallel..."
	@if command -v npx >/dev/null 2>&1; then \
		npx -y concurrently -n backend,web -c blue,green \
			"uvicorn api.main:app --reload --host 0.0.0.0 --port 8000" \
			"cd web && npm run dev"; \
	else \
		echo "npx not found — run 'make dev-backend' and 'make dev-web' in separate terminals"; \
		exit 1; \
	fi

test-backend:
	pytest -q

test-web:
	cd web && npm test

test: test-backend test-web

build:
	cd web && npm run build

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache
	rm -rf web/.next web/node_modules/.cache
