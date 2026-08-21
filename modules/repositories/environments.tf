# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

locals {
  environment_pairs = merge([
    for repository, environment_names in var.repository_environments : {
      for environment in environment_names :
      "${repository}:${environment}" => { repository = repository, environment = environment }
    }
  ]...)
  project_required_environments = toset([
    for name, environment in var.environments : name if environment.project_required
  ])
  dr_evidence_repositories = toset([
    "bootstrap",
    "github-config",
    "infrastructure-live",
    "gitops",
  ])
  dr_evidence_environments = toset(["scratch", "staging"])
  dr_evidence_environment_pairs = {
    for key, pair in local.environment_pairs : key => pair
    if contains(local.dr_evidence_repositories, pair.repository) &&
    contains(local.dr_evidence_environments, pair.environment)
  }
  dr_evidence_variable_pairs = merge([
    for pair_key, pair in local.dr_evidence_environment_pairs : {
      for name, value in var.dr_evidence_environment_variables :
      "${pair_key}:${name}" => merge(pair, { name = name, value = value, pair_key = pair_key })
    }
  ]...)
}

resource "github_repository_environment" "this" {
  for_each            = local.environment_pairs
  repository          = github_repository.this[each.value.repository].name
  environment         = each.value.environment
  wait_timer          = var.environments[each.value.environment].wait_timer
  can_admins_bypass   = false
  prevent_self_review = var.environments[each.value.environment].prevent_self_review

  dynamic "reviewers" {
    for_each = length(var.environments[each.value.environment].reviewer_teams) > 0 ? [1] : []
    content {
      teams = [for t in var.environments[each.value.environment].reviewer_teams : var.team_ids[t]]
    }
  }

  dynamic "deployment_branch_policy" {
    # GitHub rejects an explicit false/false branch-policy object. Omitting the block is the API
    # representation for environments such as `plan` that must accept pull-request merge refs.
    for_each = (
      var.environments[each.value.environment].protected_branches ||
      var.environments[each.value.environment].custom_branch_policies
    ) ? [1] : []
    content {
      protected_branches     = var.environments[each.value.environment].protected_branches
      custom_branch_policies = var.environments[each.value.environment].custom_branch_policies
    }
  }
}

check "repository_environment_branch_policies_are_valid" {
  assert {
    condition = alltrue([for _, environment in var.environments :
      !(environment.protected_branches && environment.custom_branch_policies)
    ])
    error_message = "An environment cannot select protected branches and custom branch policies simultaneously."
  }
}

resource "github_actions_environment_variable" "gcp_project" {
  for_each = { for k, v in local.environment_pairs : k => v
    if var.environments[v.environment].project_required && try(var.environment_project_ids[v.environment], "") != ""
  }
  repository    = github_repository.this[each.value.repository].name
  environment   = github_repository_environment.this[each.key].environment
  variable_name = "GCP_PROJECT_ID"
  value         = var.environment_project_ids[each.value.environment]
}

resource "github_actions_environment_variable" "dr_evidence" {
  for_each = local.dr_evidence_variable_pairs

  repository    = github_repository.this[each.value.repository].name
  environment   = github_repository_environment.this[each.value.pair_key].environment
  variable_name = each.value.name
  value         = each.value.value
}

check "dr_evidence_environment_contract_is_exact" {
  assert {
    condition = (
      toset(keys(local.dr_evidence_environment_pairs)) == toset(flatten([
        for repository in local.dr_evidence_repositories : [
          for environment in local.dr_evidence_environments : "${repository}:${environment}"
        ]
      ])) &&
      alltrue([
        for environment in local.dr_evidence_environments :
        var.environments[environment].protected_branches &&
        var.environments[environment].prevent_self_review &&
        length(var.environments[environment].reviewer_teams) > 0
      ])
    )
    error_message = "DR evidence requires exactly scratch and staging on bootstrap, github-config, infrastructure-live, and gitops, with protected branches, independent review, and self-review prevention."
  }
}

check "repository_environment_references_exist" {
  assert {
    condition     = alltrue(flatten([for _, names in var.repository_environments : [for name in names : contains(keys(var.environments), name)]]))
    error_message = "A repository environment is not declared in catalog/environments.yaml."
  }
}

check "environment_project_handoff_is_empty_or_complete" {
  assert {
    condition = length(var.environment_project_ids) == 0 || (
      toset(keys(var.environment_project_ids)) == local.project_required_environments &&
      alltrue([
        for name in local.project_required_environments :
        trimspace(try(var.environment_project_ids[name], "")) != ""
      ])
    )
    error_message = "environment_project_ids must be {} during initial governance, or a complete exact map for every project_required environment after infrastructure apply; partial or empty project IDs are forbidden."
  }
}
