# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Ring 0 exposes one stable `plan / verdict` context. The verdict succeeds credential-free for
# unaffected changes and propagates the connected speculative plan result when Terraform, state,
# trust, or plan-control paths change. Keep it in a dedicated ruleset so another repository
# cannot accidentally satisfy the Ring-0 gate.
resource "github_organization_ruleset" "required_checks_bootstrap" {
  name        = "required-checks-bootstrap"
  target      = "branch"
  enforcement = local.enforcement["required-checks-bootstrap"]

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
    repository_name {
      include = ["bootstrap"]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      required_check {
        context = "plan / verdict"
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}
