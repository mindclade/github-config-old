# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Organization secrets policy: there should be almost none.
#
# An org secret is readable by every workflow in every repository it is visible to, including
# a workflow added in a pull request. It has no expiry, no per-use audit trail, and no way to
# tell which job read it. The three better options, in order:
#
#   1. Workload Identity Federation. No secret at all — the job proves its identity with a
#      short-lived OIDC token. Everything touching GCP uses this and holds nothing.
#   2. An environment secret, gated by required reviewers. Unreadable by a job that does not
#      name the environment, so a PR cannot reach it.
#   3. GCP Secret Manager, fetched at run time via (1). Rotatable in one place, with an
#      access log naming the caller.
#
# An org secret is the fourth option, and needs a reason recorded next to it.
#
# This file therefore declares no secret VALUES. It declares the shape and scope of the ones
# that must exist, so that an undeclared org secret appearing in the UI shows up as drift.

# Non-secret org-wide configuration. Variables, not secrets — visible in logs by design, and
# kept here so a workflow does not hardcode an identifier that differs per environment.
#
# `selected`, not `private`. A private org variable is readable by every workflow in every
# private repository in the organization, which for a WIF pool number means every repository
# learns the shape of the identity federation whether or not it participates in it. Scoped to
# the managed repositories, it is readable by the repositories that actually authenticate.
#
# var.managed_repository_ids is what makes that possible, and is the reason it is passed into
# this module.
resource "github_actions_organization_variable" "wif_pool_project" {
  count = var.wif_pool_project_number != "" ? 1 : 0

  variable_name = "WIF_POOL_PROJECT_NUMBER"
  visibility    = "selected"
  value         = var.wif_pool_project_number

  selected_repository_ids = values(var.managed_repository_ids)
}

resource "github_actions_organization_variable" "artifact_registry_host" {
  variable_name = "ARTIFACT_REGISTRY_HOST"
  visibility    = "selected"
  value         = var.artifact_registry_host

  selected_repository_ids = values(var.managed_repository_ids)
}

# The WIF pool number is not optional in practice — every pipeline that touches GCP needs it.
# It is declared with a count above rather than a hard requirement so this configuration can
# be planned before bootstrap has ever been applied, which is the ordering documented in
# bootstrap/docs/first-apply.md. The check is what stops that temporary state becoming
# permanent silently.
check "wif_pool_project_number_is_set" {
  assert {
    condition     = var.wif_pool_project_number != ""
    error_message = "wif_pool_project_number is empty, so WIF_POOL_PROJECT_NUMBER is not created and every pipeline that authenticates to GCP will fail. Set it from `terraform output cicd_project_number` in the bootstrap repo."
  }
}

# ---------------------------------------------------------------------------------------
# Drift surface
# ---------------------------------------------------------------------------------------
# Terraform cannot enumerate org secrets it does not manage, so this cannot be enforced in
# code. drift.yml calls the API and fails when it finds a secret absent from this list —
# which is how an org secret added by hand in the UI becomes visible.
locals {
  expected_org_secrets = []
}

output "expected_org_secrets" {
  description = "Org secrets this configuration expects to exist. Anything else is drift."
  value       = local.expected_org_secrets
}
