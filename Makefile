SHELL := /usr/bin/env bash
.DEFAULT_GOAL := validate
PYTHON ?= python3
TERRAFORM ?= terraform
ACTIONLINT ?= actionlint
YAMLLINT ?= yamllint

.PHONY: validate lint catalog fmt fmt-check test security license-headers doctor
.PHONY: validate-production-contract workspace-remotes-check workspace-remotes-apply
.PHONY: workspace-remotes-test scripts-test

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
	@$(PYTHON) scripts/license-header-check.py --check

fmt:
	@$(TERRAFORM) fmt -recursive

test: workspace-remotes-test scripts-test
	@$(TERRAFORM) test -no-color

validate-production-contract:
	@$(PYTHON) scripts/validate-production-contract.py

doctor: workspace-remotes-check

workspace-remotes-check:
	@$(PYTHON) scripts/configure-workspace-remotes.py

workspace-remotes-apply:
	@$(PYTHON) scripts/configure-workspace-remotes.py --apply

workspace-remotes-test:
	@$(PYTHON) -m unittest -v tests/test_configure_workspace_remotes.py

scripts-test:
	@$(PYTHON) -m unittest -v tests/test_operational_scripts.py
