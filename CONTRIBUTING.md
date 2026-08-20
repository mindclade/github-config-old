# Contributing to `github-config`

Org-wide conventions are the canonical
[`CONTRIBUTING.md`](https://github.com/Mindclade/.github/blob/main/CONTRIBUTING.md).
This file covers what is different here.

*(This exists because `.github` is internal, so nothing inherits. See `SECURITY.md`.)*

## What makes this repository different

**A change here alters what everyone else can do.** A ruleset edit changes merge requirements
across the whole organization; a `team_access` edit changes who can reach what. `@security`
owns `modules/rulesets/`, `modules/policies/`, `modules/organization/`, and `modules/teams/`, and their approval is a
hard gate rather than a courtesy.

**Read the plan comment before approving.** For most repos the plan is a formality. Here it
is the review. Look specifically for `will be destroyed` and `must be replaced` — a destroyed
ruleset stops enforcing the moment it is gone, and nothing alerts.

## Introducing or widening a ruleset

Never ship straight to `active`:

```sh
terraform plan -var='ruleset_enforcement_overrides={"new-ruleset"="evaluate"}'
```

GitHub records what *would* have been blocked without blocking it, visible in the org's
rulesets insights tab. Promote once that is clean. Going straight to `active` with a wrong
required-check context blocks every merge in the organization — including the PR that would
fix it.

To hold one ruleset back while the others go live, use `ruleset_enforcement_overrides`.

## Required status checks — read this before renaming a job

The strings in `modules/rulesets/required-checks-*.tf` must equal the **job ids** in the target
repository's workflow. GitHub reports one check per *job*; a *step* reports nothing.

A context naming something that never reports is a check that is required and permanently
pending. Merges block forever, and the status gives no hint why.

```sh
# The two must agree
python3 -c "import yaml;print(sorted(yaml.safe_load(open('.github/workflows/plan.yml'))['jobs']))"
grep -rh 'context *=' modules/rulesets/*.tf
```

Note the two shapes. A repo with its own workflow reports bare job ids (`fmt`, `plan`). A repo
*calling* a reusable workflow reports `<caller job id> / <called job id>` (`plan / plan`).
Rulesets target custom properties or well-defined repository classes; do not hard-code repository names unless the provider lacks a safe property target.

## Local checks

```sh
cp backend.hcl.example backend.hcl && cp terraform.tfvars.example terraform.tfvars
terraform init -backend-config=backend.hcl
terraform fmt -recursive
terraform validate
GITHUB_TOKEN="$(gh auth token)" terraform plan
pre-commit install
pre-commit run --all-files mindclade-license-header
```

`plan` needs the same non-secret inputs as CI and a short-lived GitHub credential supplied through `GITHUB_TOKEN`. The protected workflow creates separate plan/apply GitHub App tokens at runtime; credentials are never Terraform variables or persisted in a saved plan.

## Two things that bite

**Custom properties are security-relevant.** Rulesets target `mindclade_repository_class` and related properties. Changing a repository from `production-control` or `enterprise-control` can lower its merge requirements and therefore requires security review.

**Changing `subject_claim_keys` is a trust migration.** This repository changes GitHub token subjects while `bootstrap/modules/identity/wif.tf` maps and authorizes their top-level claims. Follow `docs/oidc.md`: update the cloud side first, verify token exchange, then change the GitHub template. Optional claims such as `environment` and `job_workflow_ref` must never become organization-wide requirements unless every affected job supplies them.
