.PHONY: lint test

lint:
	python3 -m ruff check service scripts tests
	python3 scripts/lint_jenkinsfile.py

test: lint
	python3 -m pytest
	./scripts/validate_manifests.sh
