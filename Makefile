PYTHON ?= .venv/bin/python
PYTEST = $(PYTHON) -m pytest
PIP = $(PYTHON) -m pip

.PHONY: install test test-unit test-integration run

install:
	$(PIP) install -e '.[dev]'

test:
	$(PYTEST) tests

test-unit:
	$(PYTEST) tests/unit

test-integration:
	$(PYTEST) tests/integration

run:
	$(PYTHON) -m memlite.app.main
