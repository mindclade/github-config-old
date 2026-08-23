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
  merge_queue_repository_enforcement = {
    for name in keys(local.merge_queue_repositories) :
    name => local.enforcement["merge-queue"] == "disabled" ? "disabled" : try(
      var.merge_queue_repository_enforcement_overrides[name],
      "evaluate",
    )
  }
}

check "merge_queue_repository_overrides_name_eligible_repositories" {
  assert {
    condition = alltrue([
      for name in keys(var.merge_queue_repository_enforcement_overrides) :
      contains(keys(local.merge_queue_repositories), name)
    ])
    error_message = "merge_queue_repository_enforcement_overrides may name only repositories selected by the merge-queue catalog rule."
  }
}

check "merge_queue_canary_names_one_eligible_repository" {
  assert {
    condition = length(var.merge_queue_canary_required_checks) <= 1 && alltrue([
      for name in keys(var.merge_queue_canary_required_checks) :
      contains(keys(local.merge_queue_repositories), name)
    ])
    error_message = "merge_queue_canary_required_checks may name at most one repository selected by the merge-queue catalog rule."
  }
}

check "merge_queue_canary_contexts_are_exact" {
  assert {
    condition = alltrue(flatten([
      for _, contexts in var.merge_queue_canary_required_checks : [
        for context in contexts : context != "" && context == trimspace(context)
      ]
      ])) && alltrue([
      for _, contexts in var.merge_queue_canary_required_checks : length(contexts) > 0
    ])
    error_message = "Each merge-queue canary must contain at least one nonblank required-check context without surrounding whitespace."
  }
}

check "merge_queue_canary_is_active" {
  assert {
    condition = alltrue([
      for name in keys(var.merge_queue_canary_required_checks) :
      local.merge_queue_repository_enforcement[name] == "active"
    ])
    error_message = "A merge-queue canary required-check block may be configured only for a repository whose queue is active."
  }
}

resource "github_repository_ruleset" "merge_queue" {
  for_each = local.merge_queue_repositories

  name        = "merge-queue"
  repository  = each.key
  target      = "branch"
  enforcement = local.merge_queue_repository_enforcement[each.key]

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
    dynamic "required_status_checks" {
      for_each = length(lookup(var.merge_queue_canary_required_checks, each.key, [])) == 0 ? [] : [true]

      content {
        dynamic "required_check" {
          for_each = var.merge_queue_canary_required_checks[each.key]

          content {
            context        = required_check.value
            integration_id = local.github_actions_integration_id
          }
        }

        strict_required_status_checks_policy = true
        do_not_enforce_on_create             = true
      }
    }

    merge_queue {
      check_response_timeout_minutes    = 120
      grouping_strategy                 = "ALLGREEN"
      max_entries_to_build              = 1
      max_entries_to_merge              = 1
      merge_method                      = "SQUASH"
      min_entries_to_merge              = 1
      min_entries_to_merge_wait_minutes = 0
    }
  }
}

output "merge_queue_repository_enforcement" {
  description = "Effective fail-closed merge-queue enforcement by eligible repository."
  value       = local.merge_queue_repository_enforcement
}
