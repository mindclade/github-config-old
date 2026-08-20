# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
resource "github_organization_ruleset" "merge_queue" {
  name        = "merge-queue"
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
    repository_property {
      include = [{
        name            = "mindclade_repository_class"
        property_values = var.rulesets["merge-queue"].classes
        source          = "custom"
      }]
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
