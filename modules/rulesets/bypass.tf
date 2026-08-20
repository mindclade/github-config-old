# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Bypass actors are not a ruleset of their own — GitHub models bypass as a list inside each
# ruleset, so there is nothing standalone to declare. This file defines the shared lists that
# every other ruleset in this module references, which keeps "who can bypass what" answerable
# by reading one file instead of eight.
#
# Two rules, no exceptions:
#
#   1. Prefer bypass_mode = "pull_request" over "always". "pull_request" lets an actor merge
#      a PR that does not satisfy the rule; "always" lets them push directly to main with no
#      review and no record beyond the audit log. The second is a different power entirely.
#
#   2. Every entry has a named reason below. An actor nobody can justify is an actor to
#      remove — that is the whole review, and it takes a minute per quarter.
#
# actor_type is one of: RepositoryRole | Team | Integration | OrganizationAdmin
# Note that GitHub's delegated-bypass request/approve flow is configured in the UI; the
# provider only models the actor list. It is tracked in docs/enterprise-manual-controls.md.

locals {
  # Nobody. The default for anything that protects a security control.
  bypass_none = []

  # Security team, PR-scoped. Reason: security must be able to land a fix for a rule that is
  # itself blocking the fix — a bad required check, a CODEOWNERS entry pointing at a team
  # that no longer exists. Not for routine work.
  bypass_security = [
    {
      actor_id    = var.security_team_id
      actor_type  = "Team"
      bypass_mode = "pull_request"
    }
  ]

  # Platform + security, PR-scoped. Reason: incident response on delivery paths, where the
  # promotion gate is the thing standing between a broken production and a rollback.
  bypass_incident_response = [
    {
      actor_id    = var.platform_team_id
      actor_type  = "Team"
      bypass_mode = "pull_request"
    },
    {
      actor_id    = var.security_team_id
      actor_type  = "Team"
      bypass_mode = "pull_request"
    }
  ]
}
