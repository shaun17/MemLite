PYTHON ?= .venv/bin/python
PYTEST = $(PYTHON) -m pytest
PIP = $(PYTHON) -m pip

.PHONY: install test test-unit test-integration run build-plugin sync-plugin

install:
	$(PIP) install -e '.[dev]'

build-plugin:
	cd integrations/openclaw && npm install && npm run build

sync-plugin:
	bash scripts/sync_openclaw_dist.sh

test:
	$(PYTEST) tests

test-unit:
	$(PYTEST) tests/unit

test-integration:
	$(PYTEST) tests/integration

run:
	$(PYTHON) -m memlite.app.main
