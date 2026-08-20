# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

locals {
  # integrations/github 6.13 exposes merge_queue only on github_repository_ruleset, not on
  # github_organization_ruleset. Compile the catalog's class target into one repository-level
  # ruleset per matching repository until the organization resource gains schema parity.
  merge_queue_repositories = {
    for name, repository in var.repositories : name => repository
    if contains(var.rulesets["merge-queue"].classes, repository.repository_class)
  }
}

resource "github_repository_ruleset" "merge_queue" {
  for_each = local.merge_queue_repositories

  name        = "merge-queue"
  repository  = each.key
  target      = "branch"
  enforcement = local.enforcement["merge-queue"]

  dynamic "bypass_actors" {
    for_each = local.bypass_incident_response
    content {
      actor_id    = bypass_actors.value.actor_id
      actor_type  = bypass_actors.value.actor_type
      bypass_mode = bypass_actors.value.bypass_mode
    }
  }

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  rules {
    merge_queue {
      check_response_timeout_minutes    = 60
      grouping_strategy                 = "HEADGREEN"
      max_entries_to_build              = 5
      max_entries_to_merge              = 5
      merge_method                      = "SQUASH"
      min_entries_to_merge              = 1
      min_entries_to_merge_wait_minutes = 0
    }
  }
}
