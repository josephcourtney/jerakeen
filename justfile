set shell := ["bash", "-euo", "pipefail", "-c"]

ROOT := justfile_directory()

UV := "uv --cache-dir .cache/uv"
PYTHON := UV + " run python"
RUFF := UV + " run ruff"
TY := UV + " run ty"
PYTEST := UV + " run pytest"

setup:
    {{UV}} sync -U --all-groups --all-extras

syntax:
    {{PYTHON}} -m compileall "{{ROOT}}/src"
    {{PYTHON}} -m compileall "{{ROOT}}/tests"
    {{PYTHON}} -m compileall "{{ROOT}}/scripts"

proto:
    {{PYTHON}} scripts/generate_protos.py

lint:
    {{RUFF}} check --fix src tests

format:
    {{RUFF}} format src tests

typecheck:
    {{TY}} check src tests

test:
    {{PYTEST}}

test-cov:
    {{PYTEST}} --cov=jerakeen --cov-report=term-missing

check: syntax format lint typecheck test

build: proto
    {{UV}} build


clean:
  find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
  rm -rf .coverage .coverage.* coverage.xml htmlcov
  rm -rf .cache .pytest_cache .import_linter_cache
  rm -rf dist build mutants
  rm -rf **/.DS_Store 
