SHELL := /usr/bin/env bash
.DEFAULT_GOAL := validate
PYTHON ?= python3
TERRAFORM ?= terraform
ACTIONLINT ?= actionlint
YAMLLINT ?= yamllint

.PHONY: validate lint catalog fmt fmt-check test security license-headers validate-production-contract

validate: lint fmt-check catalog security license-headers validate-production-contract

lint:
	@$(ACTIONLINT) -config-file .github/actionlint.yaml .github/workflows/*.yml
	@$(YAMLLINT) --strict .

fmt-check:
	@$(TERRAFORM) fmt -check -recursive -diff

catalog:
	@$(PYTHON) scripts/validate-catalog.py

security:
	@$(PYTHON) scripts/check-access-expiry.py

license-headers:
	@./scripts/license-header-check.sh --check

fmt:
	@$(TERRAFORM) fmt -recursive

test:
	@$(TERRAFORM) test -no-color

validate-production-contract:
	@$(PYTHON) scripts/validate-production-contract.py
