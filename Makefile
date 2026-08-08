.PHONY: sync run test lint fmt typecheck check docker-build

sync:
	uv sync

run:
	uv run uvicorn line_connect.main:create_app --factory --reload --port 8000

test:
	uv run pytest

lint:
	uv run ruff check src tests

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy

check: lint typecheck test

docker-build:
	docker build -t line-connect:dev .
