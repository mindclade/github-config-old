# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Teams and their hierarchy. Repository grants live in modules/repositories — they need
# repository names, and keeping them here would couple the two modules in both directions.

# Two passes, because a team's parent must exist before the child references its id and
# Terraform cannot order a single for_each against itself. Two levels is all this supports,
# which matches the depth limit in the root catalogue: if you need a third pass, the tree has
# grown past the point where anyone can answer "who can merge this?".

resource "github_team" "parent" {
  for_each = { for k, v in var.teams : k => v if try(v.parent, null) == null }

  name        = each.key
  description = each.value.description
  privacy     = each.value.privacy
}

resource "github_team" "child" {
  for_each = { for k, v in var.teams : k => v if try(v.parent, null) != null }

  name           = each.key
  description    = each.value.description
  privacy        = each.value.privacy
  parent_team_id = github_team.parent[each.value.parent].id
}

locals {
  # Flattened lookup so nothing downstream cares which pass created a team.
  all_teams = merge(github_team.parent, github_team.child)
}

resource "github_team_settings" "review_assignment" {
  for_each = var.review_assignment_teams

  team_id = local.all_teams[each.key].id
  notify  = false

  review_request_delegation {
    algorithm    = "LOAD_BALANCE"
    member_count = 1
  }
}

# A parent named by a child but never declared fails deep in the apply with a map-lookup
# error that names neither team. Catch it at plan time.
check "declared_parents_exist" {
  assert {
    condition = alltrue([
      for k, v in var.teams :
      contains(keys(var.teams), v.parent) if try(v.parent, null) != null
    ])
    error_message = "A team names a parent that is not declared in the teams catalogue."
  }
}
