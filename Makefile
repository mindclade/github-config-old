SHELL := /usr/bin/env bash
.DEFAULT_GOAL := validate
PYTHON ?= python3
TERRAFORM ?= terraform
ACTIONLINT ?= actionlint
YAMLLINT ?= yamllint

.PHONY: validate lint catalog adoption workflow-adoption fmt fmt-check test security license-headers doctor
.PHONY: validate-production-contract validate-repository-home workspace-remotes-check workspace-remotes-apply
.PHONY: workspace-remotes-test scripts-test terraform-init-test connected-audit activation-gate
.PHONY: bootstrap-account-handoff prepare-workflow-activation prepare-workflow-pin-upgrades
.PHONY: qualify-github-platform protected-run-contract

validate: lint fmt-check catalog adoption workflow-adoption security license-headers bootstrap-account-handoff protected-run-contract validate-production-contract validate-repository-home

protected-run-contract:
	@$(PYTHON) -m unittest tests.test_protected_run

lint:
	@$(ACTIONLINT) -config-file .github/actionlint.yaml .github/workflows/*.yml
	@$(YAMLLINT) --strict .

fmt-check:
	@$(TERRAFORM) fmt -check -recursive -diff

catalog:
	@$(PYTHON) scripts/validate-catalog.py

adoption:
	@$(PYTHON) scripts/validate-adoption-plan.py

workflow-adoption:
	@$(PYTHON) scripts/render-workflow-adoption.py

qualify-github-platform:
	@$(PYTHON) scripts/qualify-github-platform.py

prepare-workflow-activation:
	@$(PYTHON) scripts/prepare-workflow-activation.py

prepare-workflow-pin-upgrades:
	@$(PYTHON) scripts/upgrade-workflow-pins.py

activation-gate:
	@$(PYTHON) scripts/validate-adoption-plan.py --activation

connected-audit:
	@$(PYTHON) scripts/audit-connected-governance.py

security:
	@$(PYTHON) scripts/check-access-expiry.py

license-headers:
	@$(PYTHON) scripts/license-header-check.py --check

bootstrap-account-handoff:
	@$(PYTHON) scripts/validate-bootstrap-account-handoff.py

fmt:
	@$(TERRAFORM) fmt -recursive

test: workspace-remotes-test scripts-test terraform-init-test
	@$(TERRAFORM) test -no-color

terraform-init-test:
	@$(TERRAFORM) init -input=false -backend=false -lockfile=readonly

validate-production-contract:
	@$(PYTHON) scripts/validate-production-contract.py

validate-repository-home:
	@$(PYTHON) scripts/validate-repository-home.py --root .

doctor: workspace-remotes-check

workspace-remotes-check:
	@$(PYTHON) scripts/configure-workspace-remotes.py

workspace-remotes-apply:
	@$(PYTHON) scripts/configure-workspace-remotes.py --apply

workspace-remotes-test:
	@$(PYTHON) -m unittest -v tests/test_configure_workspace_remotes.py

scripts-test:
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
