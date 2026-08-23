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
      output.rulesets["required-checks-gitops"].enforcement == "evaluate" &&
      output.rulesets["required-checks-gitops"].repositories == ["gitops"]
    )
    error_message = "GitOps merge-queue checks must remain evaluate until the staged queue is qualified."
  }

  assert {
    condition = (
      output.rulesets["required-checks-github-config"].enforcement == "evaluate" &&
      output.governance_activation.gates.github_config_verdict_observed == "blocked" &&
      output.rulesets["required-checks-github-config"].repositories == ["github-config"] &&
      output.rulesets["required-checks-tf"].repositories == ["infrastructure-live"]
    )
    error_message = "github-config's path-aware verdict must remain evaluate while blocked and separate from infrastructure-live's raw plan."
  }

  assert {
    condition = (
      contains(
        ["evaluate", "active"],
        output.rulesets["required-checks-infra-static"].enforcement,
      ) &&
      (
        output.rulesets["required-checks-infra-static"].enforcement != "active" ||
        (
          output.governance_activation.gates.monorepo_merge_group_full_graph_observed == "qualified" &&
          output.governance_activation.gates.rulesets_connected_audit == "qualified"
        )
      ) &&
      output.rulesets["required-checks-infra-static"].repositories == ["mindclade-internal-monorepo"]
    )
    error_message = "infra-static may become active only for the canonical monorepo after merge-group and connected ruleset evidence is qualified."
  }

  assert {
    condition = (
      contains(
        ["evaluate", "active"],
        output.rulesets["required-checks-mixed"].enforcement,
      ) &&
      output.rulesets["required-checks-mixed"].language_profiles == ["mixed"] &&
      (
        output.rulesets["required-checks-mixed"].enforcement != "active" ||
        (
          output.governance_activation.gates.monorepo_bazel_verdict_observed == "qualified" &&
          output.governance_activation.gates.monorepo_merge_group_full_graph_observed == "qualified" &&
          output.governance_activation.gates.rulesets_connected_audit == "qualified"
        )
      )
    )
    error_message = "Mixed-language checks may become active only for the mixed profile after every activation gate is qualified."
  }

  assert {
    condition = (
      output.governance_activation.gates.infrastructure_cost_verdict_ready == "blocked" &&
      output.required_check_readiness.contexts["infrastructure-cost"].status == "blocked" &&
      output.required_check_readiness.contexts["infrastructure-cost"].qualified_context == null &&
      output.required_check_readiness.contexts["infrastructure-cost"].target_ruleset == "required-checks-tf" &&
      toset(output.required_check_readiness.contexts["infrastructure-cost"].required_events) == toset([
        "pull_request",
        "merge_group",
      ])
    )
    error_message = "Infrastructure cost enforcement must remain blocked until one stable verdict reports on pull requests and merge groups."
  }

  assert {
    condition = (
      output.merge_queue_readiness.schema_version == 1 &&
      [for contract in output.merge_queue_readiness.rollout_order : contract.repository] == [
        "mindclade-internal-monorepo",
        "gitops",
        "infrastructure-live",
      ] &&
      alltrue([
        for contract in output.merge_queue_readiness.rollout_order :
        contract.github_actions_integration_id == 15368 && contract.status == "blocked"
      ])
    )
    error_message = "Merge-queue readiness must start blocked in exact repository order and pin the GitHub Actions integration."
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

  assert {
    condition = (
      toset(keys(output.runner_groups)) == toset([
        "mindclade-arc-artifact-authority",
        "mindclade-arc-ci",
      ]) &&
      toset(output.runner_groups["mindclade-arc-artifact-authority"].workflows) == toset([
        "mindclade/.github/.github/workflows/reusable-arc-wif-canary.yml@v5.0.0",
        "mindclade/.github/.github/workflows/reusable-arc-oci-build.yml@v5.0.0",
        "mindclade/.github/.github/workflows/reusable-arc-oci-qualify.yml@v5.0.0",
        "mindclade/.github/.github/workflows/reusable-arc-qualification-attest.yml@v5.0.0",
      ]) &&
      output.runner_groups["mindclade-arc-ci"].workflows == [
        "mindclade/mindclade-internal-monorepo/.github/workflows/presubmit.yml@refs/heads/main",
      ]
    )
    error_message = "ARC artifact authority and presubmit must use separate groups restricted to the exact workflows that define their jobs."
  }
}
