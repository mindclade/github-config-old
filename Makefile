SHELL := /usr/bin/env bash
.DEFAULT_GOAL := validate
PYTHON ?= python3
TERRAFORM ?= terraform
ACTIONLINT ?= actionlint
YAMLLINT ?= yamllint

.PHONY: validate lint catalog adoption fmt fmt-check test security license-headers doctor
.PHONY: validate-production-contract validate-repository-home validate-repository-policy workspace-remotes-check workspace-remotes-apply
.PHONY: workspace-remotes-test scripts-test terraform-init-test connected-audit activation-gate

validate: lint fmt-check catalog adoption security license-headers validate-production-contract validate-repository-policy validate-repository-home

lint:
	@$(ACTIONLINT) -config-file .github/actionlint.yaml .github/workflows/*.yml
	@$(YAMLLINT) --strict .

fmt-check:
	@$(TERRAFORM) fmt -check -recursive -diff

catalog:
	@$(PYTHON) scripts/validate-catalog.py

adoption:
	@$(PYTHON) scripts/validate-adoption-plan.py

activation-gate:
	@$(PYTHON) scripts/validate-adoption-plan.py --activation

connected-audit:
	@$(PYTHON) scripts/audit-connected-governance.py

security:
	@$(PYTHON) scripts/check-access-expiry.py

license-headers:
	@$(PYTHON) scripts/license-header-check.py --check

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

validate-repository-policy:
	@$(PYTHON) scripts/validate-repository-policy.py --root .

doctor: workspace-remotes-check

workspace-remotes-check:
	@$(PYTHON) scripts/configure-workspace-remotes.py

workspace-remotes-apply:
	@$(PYTHON) scripts/configure-workspace-remotes.py --apply

workspace-remotes-test:
	@$(PYTHON) -m unittest -v tests/test_configure_workspace_remotes.py

scripts-test:
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
