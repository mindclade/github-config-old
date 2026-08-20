# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Ring 0 has one repository-local, credentialed plan job. Its context is `speculative`, not the
# `fmt`/`validate`/`plan` contract used by github-config and infrastructure-live. Keep it in a
# dedicated ruleset so neither repository can accidentally satisfy the other's merge gate.
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
        context = "speculative"
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}
