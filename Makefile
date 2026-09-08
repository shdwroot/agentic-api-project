.PHONY: install test lint run generate example test-generated docker

ifeq ($(OS),Windows_NT)
UV := cmd.exe /d /c scripts/uv-local.cmd
else
UV := ./scripts/uv-local
endif
CONTEXT ?= examples/exception_service_context.yaml
OUTPUT ?= generated
RESULT ?= $(OUTPUT)/result.json

install:
	$(UV) sync --extra dev

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

run:
	$(UV) run uvicorn agentic_api.main:app --reload --host 127.0.0.1 --port 8088

generate:
	$(UV) run agentic-soap generate --context $(CONTEXT) --output $(OUTPUT) --result-json $(RESULT)

example: generate

test-generated:
	$(UV) run pytest $(OUTPUT)/generated_tests -m "not live"

docker:
	docker compose up --build
