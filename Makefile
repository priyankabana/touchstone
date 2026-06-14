PYTHON ?= python
PIP ?= $(PYTHON) -m pip
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: install inject seed demo headless eval test preflight snapshot clean

install:
	$(PIP) install -r requirements.txt pytest

inject:
	$(PYTHON) -m ingest.inject

seed:
	$(PYTHON) -m store.seed

demo: seed
	uvicorn api.main:app --host $(HOST) --port $(PORT)

headless:
	$(PYTHON) run_demo.py
	OFFLINE=1 $(PYTHON) -m agent.run_agent

eval:
	$(PYTHON) -m evals.metrics

test:
	$(PYTHON) -m pytest tests/ -q

preflight:
	$(PYTHON) scripts/preflight.py

snapshot:
	OFFLINE=0 LIVE=1 $(PYTHON) scripts/snapshot.py

clean:
	rm -f data/touchstone.db
	rm -rf .pytest_cache touchstone-sandbox
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
