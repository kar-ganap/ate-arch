.PHONY: test lint typecheck all

all: test lint typecheck

test:
	uv run pytest tests/unit -v

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

typecheck:
	uv run mypy src/
