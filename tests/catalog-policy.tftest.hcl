# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

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
      output.actions_policy.sha_pinning_required &&
      contains(
        output.actions_policy.allowed_action_patterns,
        "mindclade/.github/actions/validate-repository-home@*"
      )
    )
    error_message = "Actions must be selected-only, read-by-default, SHA-pinned, and include the repository-home validator."
  }

  assert {
    condition = toset(output.oidc_policy.subject_claim_keys) == toset([
      "repository_owner_id",
      "repository_id",
      "repository",
      "workflow_ref",
      "ref",
    ])
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
    condition = (
      !output.oidc_policy.repository_opt_in &&
      output.oidc_policy.require_immutable_default_subject &&
      output.oidc_policy.require_protected_environment_for_sensitive_plan &&
      output.oidc_policy.require_protected_environment_for_apply
    )
    error_message = "Immutable default subjects and protected plan/apply environments must remain enabled."
  }

  assert {
    condition     = output.rulesets["ruleset-workflows"].workflow_ref == "refs/tags/v5.0.0"
    error_message = "Mandatory workflow enforcement must use the controlled v5.0.0 release tag."
  }

  assert {
    condition = (
      output.rulesets["release-tag-creation"].enforcement == "evaluate" &&
      output.rulesets["tag-protection"].enforcement == "active" &&
      output.governance_activation.gates.release_tag_creation_control_qualified == "blocked"
    )
    error_message = "Release-tag creation must remain staged until qualified while immutable tag protection stays active."
  }

  assert {
    condition = (
      !output.repository_classes["enterprise-control"].merge_queue &&
      toset(output.rulesets["merge-queue"].classes) == toset([
        "production-control",
        "source-monorepo",
      ])
    )
    error_message = "Merge queue must remain limited to production-control and source-monorepo repositories."
  }

  assert {
    condition = (
      output.rulesets["required-checks-bootstrap"].enforcement == "evaluate" &&
      output.rulesets["required-checks-bootstrap"].repositories == ["bootstrap"]
    )
    error_message = "Ring-0 plan / verdict must remain evaluate-mode until both path outcomes are observed."
  }

  assert {
    condition = (
      output.rulesets["required-checks-gitops"].enforcement == "active" &&
      output.rulesets["required-checks-gitops"].repositories == ["gitops"]
    )
    error_message = "GitOps merge-queue changes must require repository-local static checks."
  }

  assert {
    condition = (
      output.rulesets["required-checks-github-config"].enforcement == "active" &&
      output.rulesets["required-checks-github-config"].repositories == ["github-config"] &&
      output.rulesets["required-checks-tf"].repositories == ["infrastructure-live"]
    )
    error_message = "github-config's path-aware verdict and infrastructure-live's raw plan must remain in separate rulesets."
  }

  assert {
    condition = (
      output.rulesets["required-checks-infra-static"].enforcement == "evaluate" &&
      output.rulesets["required-checks-infra-static"].repositories == ["mindclade-internal-monorepo"]
    )
    error_message = "infra-static must remain an evaluate-mode, canonical-monorepo-only source contract until observed on pull_request and merge_group."
  }

  assert {
    condition = (
      output.rulesets["required-checks-mixed"].enforcement == "evaluate" &&
      output.rulesets["required-checks-mixed"].language_profiles == ["mixed"]
    )
    error_message = "Mixed-language checks must remain evaluate-mode and target only the mixed profile until every context is observed."
  }

  assert {
    condition = (
      output.rulesets["required-checks-nix"].enforcement == "evaluate" &&
      toset(output.rulesets["required-checks-nix"].repositories) == toset([
        ".github",
        ".github-private",
        "bootstrap",
        "github-config",
        "gitops",
        "infrastructure-live",
        "mindclade-internal-monorepo",
      ])
    )
    error_message = "Nix qualification must remain evaluate-mode and cover exactly the managed estate until rollout evidence is reviewed."
  }
}
