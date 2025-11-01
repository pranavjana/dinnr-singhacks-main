PYTHON ?= python3
APP_MODULE ?= AML_triage.api.router:create_app
APP_CONFIG ?= $(PWD)/src/AML_triage/config/app.yaml
UVICORN ?= uvicorn

.PHONY: run run-dev test test-all contracts lint fmt

run:
	APP_CONFIG=$(APP_CONFIG) OFFLINE_MODE=$${OFFLINE_MODE:-true} $(UVICORN) $(APP_MODULE) --factory --host 0.0.0.0 --port $${PORT:-8000}

run-dev:
	APP_CONFIG=$(APP_CONFIG) OFFLINE_MODE=$${OFFLINE_MODE:-true} $(UVICORN) $(APP_MODULE) --factory --reload --host 0.0.0.0 --port $${PORT:-8000}

test:
	$(PYTHON) -m pytest tests/AML_triage -m "not contract"

test-all:
	$(PYTHON) -m pytest tests/AML_triage

contracts:
	schemathesis run http://localhost:$${PORT:-8000}/openapi.json

lint:
	$(PYTHON) -m ruff check src/AML_triage tests/AML_triage

fmt:
	$(PYTHON) -m ruff format src/AML_triage tests/AML_triage
