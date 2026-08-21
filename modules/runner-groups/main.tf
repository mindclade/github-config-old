# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

resource "github_actions_runner_group" "this" {
  for_each = var.runner_groups

  name                       = each.key
  visibility                 = each.value.visibility
  allows_public_repositories = each.value.allowsPublicRepositories
  restricted_to_workflows    = each.value.restrictedToWorkflows
  selected_repository_ids    = [for repository in each.value.repositories : var.repository_ids[repository]]
  selected_workflows         = each.value.workflows
}

check "runner_group_repositories_exist" {
  assert {
    condition = alltrue(flatten([
      for _, group in var.runner_groups : [
        for repository in group.repositories : contains(keys(var.repository_ids), repository)
      ]
    ]))
    error_message = "A runner group references a repository outside the managed estate."
  }
}
