# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Membership is derived from the IdP export, not written here.
#
# Two reasons this is not a hand-maintained list. Offboarding: removing someone from the IdP
# has to remove them everywhere, and a hand-kept copy is the file people forget. Audit: "who
# had access on this date" must be answerable from one system, not reconciled across two.
#
# The export is produced by scripts/export-idp-groups.sh into the path given by
# var.idp_export_path (idp/team-members.json at the repo root).
#
# WHO RUNS IT. .github/workflows/idp-sync.yml, nightly, in --check mode: it compares the
# committed file against the directory and opens an issue when they diverge, with the correct
# file attached as an artifact. It does NOT commit — writing to the default branch of the
# repository that governs the organization would need a standing contents:write grant, and a
# membership change is exactly the diff a human should approve. So the commit is manual and
# the detection is not.
#
# That distinction used to be missing in the worse direction: this comment said a scheduled
# job committed the file, no such job existed, and the fileexists() guard below meant a plan
# succeeded and created zero memberships. A fully governed organization with nobody in it,
# and nothing anywhere saying so.
#
# A human editing that file will have it overwritten by the next export, which is the
# intended behaviour.
#
# Shape:
#   {
#     "org_members":  [{"username": "alice", "role": "member"}],
#     "team_members": {"platform": [{"username": "alice", "role": "maintainer"}]}
#   }

locals {
  # fileexists() keeps `terraform validate` and a first plan working before the first sync
  # has ever run. Without it this repo cannot be initialised until the IdP export exists,
  # which is a bootstrap ordering problem nobody needs.
  idp_export = fileexists(var.idp_export_path) ? jsondecode(file(var.idp_export_path)) : {
    org_members  = []
    team_members = {}
  }

  org_members = {
    for m in try(local.idp_export.org_members, []) : m.username => m
  }

  team_member_pairs = merge([
    for team, members in try(local.idp_export.team_members, {}) : {
      for m in members : "${team}:${m.username}" => {
        team     = team
        username = m.username
        role     = try(m.role, "member")
      }
    }
  ]...)
}

resource "github_membership" "this" {
  for_each = local.org_members

  username = each.value.username
  role     = try(each.value.role, "member")

  # Leaving someone as an outside collaborator on removal is worse than removing them: it
  # looks like revocation in the members list while access continues.
  downgrade_on_destroy = false
}

resource "github_team_membership" "this" {
  for_each = local.team_member_pairs

  team_id  = local.all_teams[each.value.team].id
  username = each.value.username
  role     = each.value.role

  depends_on = [github_membership.this]
}

# A membership entry naming a team that does not exist fails deep inside the apply with an
# unhelpful map-lookup error. Catch it at plan time and name the offender.
check "idp_teams_exist" {
  assert {
    condition = alltrue([
      for _, m in local.team_member_pairs : contains(keys(var.teams), m.team)
    ])
    error_message = "The IdP export references a team that is not declared in locals.teams. Add the team here, or fix the group mapping in the IdP."
  }
}
