# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Required status checks for Go repositories, selected by the `language` custom property.
#
# Why by property rather than by name: a required check naming a job that never runs blocks
# merges forever with a permanently pending status. Scoping by language means a repo only
# inherits checks its CI actually produces, and a repo that changes language changes checks
# by editing one property.

resource "github_organization_ruleset" "required_checks_go" {
  name        = "required-checks-go"
  target      = "branch"
  enforcement = local.enforcement["required-checks-go"]

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
      include = [
        {
          name            = "mindclade_language_profile"
          property_values = ["go", "mixed"]
          source          = "custom"
        }
      ]
    }
  }

  rules {
    required_status_checks {
      # The context string must match the JOB NAME as GitHub reports it, which for a called
      # reusable workflow is "<caller job id> / <called job id>". Getting this wrong produces
      # a check that is required and never satisfied.
      required_check {
        context        = "ci / build"
        integration_id = local.github_actions_integration_id
      }

      # Was "CodeQL", which nothing in this org can produce. Two things make the real context
      # longer than the bare name:
      #
      #   - it comes from a called reusable workflow, so it carries the "<caller> / <called>"
      #     prefix like the Go check above — here `codeql-go` calling reusable-codeql's `analyze`;
      #   - `analyze` is a matrix over languages, and GitHub appends the matrix value to each
      #     check run. There is no aggregate "codeql-go / analyze" run to require.
      #
      # Only the `go` leg is required. This ruleset also covers `mindclade_language_profile = mixed` repos, which
      # additionally produce `(python)` and `(javascript-typescript)` legs — but requiring those
      # would block a pure-Go repo forever on checks its CI never runs. The `go` leg is the one
      # every repository this ruleset targets is guaranteed to emit.
      required_check {
        context        = "codeql-go / analyze (go)"
        integration_id = local.github_actions_integration_id
      }

      # Re-run checks against the merge result, not the branch head. Without this, two PRs
      # that each pass alone can merge into a broken main.
      strict_required_status_checks_policy = true

      # A branch created and immediately opened as a PR has no check runs yet; enforcing on
      # create just adds a retry loop.
      do_not_enforce_on_create = true
    }
  }
}
