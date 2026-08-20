SHELL := /usr/bin/env bash
.DEFAULT_GOAL := validate
.PHONY: validate catalog fmt test security
validate: catalog validate-production-contract
	@python3 scripts/validate-catalog.py
	@python3 scripts/check-access-expiry.py
	@./scripts/license-header-check.sh --check
catalog:
	@python3 scripts/validate-catalog.py
fmt:
	@terraform fmt -recursive
test:
	@terraform test
security:
	@python3 scripts/check-access-expiry.py

.PHONY: validate-production-contract
validate-production-contract:
	python3 scripts/validate-production-contract.py
