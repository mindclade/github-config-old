# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
locals {
  environment_pairs = merge([
    for repository, environment_names in var.repository_environments : {
      for environment in environment_names :
      "${repository}:${environment}" => { repository = repository, environment = environment }
    }
  ]...)
}

resource "github_repository_environment" "this" {
  for_each = local.environment_pairs
  repository  = github_repository.this[each.value.repository].name
  environment = each.value.environment
  wait_timer          = var.environments[each.value.environment].wait_timer
  can_admins_bypass   = false
  prevent_self_review = var.environments[each.value.environment].prevent_self_review

  dynamic "reviewers" {
    for_each = length(var.environments[each.value.environment].reviewer_teams) > 0 ? [1] : []
    content {
      teams = [for t in var.environments[each.value.environment].reviewer_teams : var.team_ids[t]]
    }
  }

  deployment_branch_policy {
    protected_branches     = var.environments[each.value.environment].protected_branches
    custom_branch_policies = !var.environments[each.value.environment].protected_branches
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

check "repository_environment_references_exist" {
  assert {
    condition = alltrue(flatten([for _, names in var.repository_environments : [for name in names : contains(keys(var.environments), name)]]))
    error_message = "A repository environment is not declared in catalog/environments.yaml."
  }
}

check "project_environments_have_projects" {
  assert {
    condition = alltrue([for _, v in local.environment_pairs :
      !var.environments[v.environment].project_required || try(var.environment_project_ids[v.environment], "") != ""
    ])
    error_message = "An environment marked project_required has no environment_project_ids entry."
  }
}
