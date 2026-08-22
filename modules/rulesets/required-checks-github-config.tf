# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# github-config exposes one stable connected-plan verdict. The verdict succeeds without cloud
# credentials for documentation-only changes and propagates the protected plan result for
# Terraform, state, trust, and plan-control changes.
resource "github_organization_ruleset" "required_checks_github_config" {
  name        = "required-checks-github-config"
  target      = "branch"
  enforcement = local.enforcement["required-checks-github-config"]

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
      include = ["github-config"]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      required_check { context = "fmt" }
      required_check { context = "validate" }
      required_check { context = "plan / verdict" }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }

  lifecycle {
    precondition {
      condition = (
        local.enforcement["required-checks-github-config"] != "active" ||
        var.github_config_verdict_observed
      )
      error_message = "required-checks-github-config cannot become active before both path-aware plan verdict outcomes are observed."
    }
  }
}
