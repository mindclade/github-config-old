# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "catalog_path" {
  description = "Directory holding the authoritative YAML catalog."
  type        = string
}

locals {
  repositories       = yamldecode(file("${var.catalog_path}/repositories.yaml"))
  repository_classes = yamldecode(file("${var.catalog_path}/repository-classes.yaml"))
  teams              = yamldecode(file("${var.catalog_path}/teams.yaml"))
  team_access        = yamldecode(file("${var.catalog_path}/access.yaml"))
  environments       = yamldecode(file("${var.catalog_path}/environments.yaml"))
  rulesets           = yamldecode(file("${var.catalog_path}/rulesets.yaml"))
  actions_policy     = yamldecode(file("${var.catalog_path}/actions-policy.yaml"))
  oidc_policy        = yamldecode(file("${var.catalog_path}/oidc-policy.yaml"))
  custom_properties  = yamldecode(file("${var.catalog_path}/custom-properties.yaml"))
  runner_groups      = yamldecode(file("${var.catalog_path}/runner-groups.yaml"))
  github_apps        = yamldecode(file("${var.catalog_path}/github-apps.yaml"))
}

check "artifact_authority_runner_group_is_exact" {
  assert {
    condition = (
      toset(keys(local.runner_groups)) == toset(["mindclade-arc-artifact-authority"]) &&
      local.runner_groups["mindclade-arc-artifact-authority"].visibility == "selected" &&
      local.runner_groups["mindclade-arc-artifact-authority"].allowsPublicRepositories == false &&
      local.runner_groups["mindclade-arc-artifact-authority"].restrictedToWorkflows == true &&
      toset(local.runner_groups["mindclade-arc-artifact-authority"].repositories) == toset(["mindclade-internal-monorepo"]) &&
      toset(local.runner_groups["mindclade-arc-artifact-authority"].workflows) == toset([
        "mindclade/mindclade-internal-monorepo/.github/workflows/release.yml@refs/heads/main"
      ])
    )
    error_message = "ARC artifact authority must be private, selected to the monorepo, and restricted to the exact trusted-main release workflow."
  }
}

check "github_app_installation_contracts_are_exact" {
  assert {
    condition = (
      toset(keys(local.github_apps)) == toset([
        "mindclade-arc",
        "mindclade-policy-sync",
        "mindclade-release-promoter",
        "mindclade-production-qualification-reader",
      ]) &&
      toset(local.github_apps["mindclade-arc"].repositories) == toset(["mindclade-internal-monorepo"]) &&
      toset(local.github_apps["mindclade-release-promoter"].repositories) == toset(["gitops"]) &&
      local.github_apps["mindclade-arc"].organizationPermissions.selfHostedRunners == "write" &&
      local.github_apps["mindclade-release-promoter"].repositoryPermissions.contents == "write" &&
      local.github_apps["mindclade-release-promoter"].repositoryPermissions.pullRequests == "write" &&
      toset(local.github_apps["mindclade-policy-sync"].repositories) == toset([
        ".github-private", "bootstrap", "github-config", "gitops",
        "infrastructure-live", "mindclade-internal-monorepo"
      ]) &&
      local.github_apps["mindclade-policy-sync"].organizationPermissions == {} &&
      local.github_apps["mindclade-policy-sync"].repositoryPermissions == {
        contents     = "write"
        metadata     = "read"
        pullRequests = "write"
      } &&
      toset(local.github_apps["mindclade-production-qualification-reader"].repositories) == toset([
        ".github", ".github-private", "bootstrap", "github-config",
        "infrastructure-live", "gitops", "mindclade-internal-monorepo"
      ]) &&
      local.github_apps["mindclade-production-qualification-reader"].organizationPermissions == {} &&
      local.github_apps["mindclade-production-qualification-reader"].repositoryPermissions == {
        actions  = "read"
        contents = "read"
        metadata = "read"
      }
    )
    error_message = "GitHub App installation or permission contract exceeds the ARC, promoter, or qualification least-privilege boundary."
  }
}

check "estate_is_complete" {
  assert {
    condition = toset(keys(local.repositories)) == toset([
      ".github", ".github-private", "github-config", "bootstrap", "infrastructure-live", "gitops", "mindclade-internal-monorepo"
    ])
    error_message = "repositories.yaml must declare exactly the seven repositories in the enterprise platform blueprint."
  }
}

check "default_branches_are_main" {
  assert {
    condition     = alltrue([for _, repository in local.repositories : repository.default_branch == "main"])
    error_message = "Every managed repository must declare main as its default branch."
  }
}

check "repository_references_are_valid" {
  assert {
    condition     = alltrue([for _, r in local.repositories : contains(keys(local.repository_classes), r.repository_class)])
    error_message = "A repository uses an undeclared repository_class."
  }
  assert {
    condition     = alltrue([for _, r in local.repositories : contains(keys(local.teams), r.owner_team)])
    error_message = "A repository uses an undeclared owner_team."
  }
  assert {
    condition     = alltrue(flatten([for _, r in local.repositories : [for e in r.environments : contains(keys(local.environments), e)]]))
    error_message = "A repository names an undeclared environment."
  }
}

check "control_repository_visibility" {
  assert {
    condition = alltrue([
      local.repositories["github-config"].visibility == "private",
      local.repositories[".github-private"].visibility == "private",
      local.repositories["bootstrap"].visibility == "private",
      local.repositories["infrastructure-live"].visibility == "private",
      local.repositories["gitops"].visibility == "internal",
      local.repositories["mindclade-internal-monorepo"].visibility == "internal"
    ])
    error_message = "Control-repository visibility differs from the enterprise platform blueprint."
  }
  assert {
    condition     = alltrue([for _, r in local.repositories : r.visibility != "public"])
    error_message = "Public visibility requires a separate security/IP/license approval and is prohibited in this catalog."
  }
}

check "production_authority_is_explicit" {
  assert {
    condition = alltrue([for _, r in local.repositories :
      r.production_authority == "false" || contains(["enterprise-control", "production-control"], r.repository_class)
    ])
    error_message = "Only enterprise-control or production-control repositories may have production authority."
  }
}

check "access_references_are_valid" {
  assert {
    condition     = alltrue([for repo, _ in local.team_access : contains(keys(local.repositories), repo)])
    error_message = "access.yaml references an undeclared repository."
  }
  assert {
    condition     = alltrue(flatten([for _, grants in local.team_access : [for team, _ in grants : contains(keys(local.teams), team)]]))
    error_message = "access.yaml references an undeclared team."
  }
  assert {
    condition     = alltrue([for name, t in local.teams : try(t.parent, null) == null || contains(keys(local.teams), t.parent)])
    error_message = "A team parent is undeclared."
  }
  assert {
    condition     = alltrue(flatten([for _, e in local.environments : [for team in e.reviewer_teams : contains(keys(local.teams), team)]]))
    error_message = "An environment reviewer team is undeclared."
  }
}

check "owner_teams_can_maintain_their_repositories" {
  assert {
    condition = alltrue([
      for name, repository in local.repositories :
      contains(["maintain"], try(local.team_access[name][repository.owner_team], ""))
    ])
    error_message = "Every repository owner_team must have maintain access."
  }
}

check "actions_policy_is_least_privilege" {
  assert {
    condition = alltrue([
      local.actions_policy.enabled_repositories == "all",
      local.actions_policy.allowed_actions == "selected",
      local.actions_policy.default_workflow_permissions == "read",
      local.actions_policy.can_approve_pull_request_reviews == false,
      local.actions_policy.sha_pinning_required == true,
      local.actions_policy.github_owned_allowed == false,
      local.actions_policy.verified_creator_allowed == false,
    ])
    error_message = "catalog/actions-policy.yaml weakens the Mindclade Actions baseline."
  }
  assert {
    condition     = length(local.actions_policy.allowed_action_patterns) > 0
    error_message = "The selected Actions policy requires an explicit allowlist."
  }
}

check "oidc_policy_uses_universal_claims" {
  assert {
    condition = toset(local.oidc_policy.subject_claim_keys) == toset([
      "repository_owner_id",
      "repository_id",
      "repository",
      "workflow_ref",
      "ref",
    ])
    error_message = "OIDC subject claims must be universal across direct and reusable workflow jobs."
  }
  assert {
    condition = toset(local.oidc_policy.required_wif_attribute_claims) == toset([
      "repository_owner_id",
      "repository_id",
      "repository",
      "workflow_ref",
      "ref",
      "event_name",
    ])
    error_message = "OIDC WIF claim contract differs from bootstrap."
  }
  assert {
    condition = alltrue([
      !local.oidc_policy.repository_opt_in,
      local.oidc_policy.require_immutable_default_subject,
      local.oidc_policy.require_trusted_owner_id,
      local.oidc_policy.require_repository_id,
      local.oidc_policy.require_workflow_ref,
      local.oidc_policy.require_ref,
      local.oidc_policy.require_protected_environment_for_sensitive_plan,
      local.oidc_policy.require_protected_environment_for_apply,
      local.oidc_policy.explicit_audience_required,
    ])
    error_message = "OIDC policy must preserve immutable default subjects and every required trust control."
  }
}

check "custom_properties_cover_repository_metadata" {
  assert {
    condition = toset(keys(local.custom_properties)) == toset([
      "mindclade_repository_class",
      "mindclade_owner_team",
      "mindclade_criticality",
      "mindclade_data_classification",
      "mindclade_production_authority",
      "mindclade_ci_profile",
      "mindclade_language_profile",
      "mindclade_lifecycle",
    ])
    error_message = "Custom-property inventory differs from the repository metadata contract."
  }
  assert {
    condition = alltrue([
      for _, property in local.custom_properties :
      property.type == "single_select" &&
      property.required == true &&
      property.values_editable_by == "org_actors" &&
      contains(property.values, property.default_value)
    ])
    error_message = "Custom properties must be required, organization-controlled single-select values with valid defaults."
  }
}

check "ruleset_catalog_matches_the_implementation" {
  assert {
    condition = toset(keys(local.rulesets)) == toset([
      "baseline-all",
      "legal-policy-paths",
      "merge-queue",
      "protected-paths",
      "release-authority-paths",
      "release-tag-creation",
      "push-blocklist",
      "required-checks-bootstrap",
      "required-checks-gitops",
      "required-checks-go",
      "required-checks-infra-static",
      "required-checks-mixed",
      "required-checks-nix",
      "required-checks-tf",
      "required-checks-tf-static",
      "required-checks-tf-tests",
      "ruleset-workflows",
      "tag-protection",
    ])
    error_message = "catalog/rulesets.yaml and modules/rulesets must change together."
  }
  assert {
    condition = alltrue([
      for _, ruleset in local.rulesets :
      contains(["active", "evaluate", "disabled"], ruleset.enforcement)
    ])
    error_message = "A ruleset has an invalid enforcement mode."
  }
}

output "repositories" { value = local.repositories }
output "repository_classes" { value = local.repository_classes }
output "teams" { value = local.teams }
output "team_access" { value = local.team_access }
output "environments" { value = local.environments }
output "rulesets" { value = local.rulesets }
output "actions_policy" { value = local.actions_policy }
output "oidc_policy" { value = local.oidc_policy }
output "custom_properties" { value = local.custom_properties }
output "runner_groups" { value = local.runner_groups }
output "github_apps" { value = local.github_apps }
