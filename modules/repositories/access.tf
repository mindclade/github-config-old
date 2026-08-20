# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Team-to-repository grants.
#
# These live here rather than in modules/teams because they need repository names. Putting
# them in teams would make the two modules depend on each other in both directions; this way
# teams exports ids, repositories consumes them, and the arrow points one way.

locals {
  # (repo, team) pairs, keyed for a stable for_each.
  repo_team_grants = merge([
    for repo, grants in var.team_access : {
      for team, permission in grants :
      "${repo}:${team}" => { repository = repo, team = team, permission = permission }
    }
  ]...)
}

resource "github_team_repository" "this" {
  for_each = local.repo_team_grants

  team_id    = var.team_ids[each.value.team]
  repository = github_repository.this[each.value.repository].name
  permission = each.value.permission
}

# A grant naming a repository or team that does not exist fails mid-apply with a map-lookup
# error naming neither. Catch both at plan time.
check "grants_reference_declared_entities" {
  assert {
    condition = alltrue([
      for _, g in local.repo_team_grants :
      contains(keys(var.repositories), g.repository) && contains(keys(var.team_ids), g.team)
    ])
    error_message = "team_access references a repository or team that is not declared."
  }
}
