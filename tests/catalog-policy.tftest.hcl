# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
variables {
  catalog_path = "catalog"
}

run "policy_catalog_is_production_grade" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = (
      output.actions_policy.default_workflow_permissions == "read" &&
      output.actions_policy.allowed_actions == "selected" &&
      output.actions_policy.sha_pinning_required
    )
    error_message = "Actions must be selected-only, read-by-default, and SHA-pinned."
  }

  assert {
    condition = setequals(toset(output.oidc_policy.subject_claim_keys), toset([
      "repository_owner_id",
      "repository_id",
      "repository",
      "workflow_ref",
      "ref",
    ]))
    error_message = "OIDC subject policy contains missing or optional claims."
  }

  assert {
    condition = (
      !contains(output.oidc_policy.subject_claim_keys, "environment") &&
      !contains(output.oidc_policy.subject_claim_keys, "job_workflow_ref")
    )
    error_message = "Optional OIDC claims cannot be mandatory organization-wide."
  }

  assert {
    condition = output.rulesets["ruleset-workflows"].workflow_ref == "refs/tags/v3.0.0"
    error_message = "Mandatory workflow enforcement must use the controlled v3.0.0 release tag."
  }
}
