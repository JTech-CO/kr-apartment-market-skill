.PHONY: install test lint validate build run-http

install:
	python -m pip install -e '.[dev]'

test:
	python -m pytest tests/runtime

lint:
	python -m ruff check src tests/runtime

validate:
	python scripts/validate_runtime.py

build:
	python -m build

run-http:
	kr-apartment-market --transport streamable-http --host 127.0.0.1 --port 8765
