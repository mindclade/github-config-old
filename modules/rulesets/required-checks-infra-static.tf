# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Credential-free Kubernetes and GitOps validation emitted by the canonical monorepo on both
# pull_request and merge_group. Keep this name-scoped: no other repository is guaranteed to
# publish the exact `infra-static` context.
resource "github_organization_ruleset" "required_checks_infra_static" {
  name        = "required-checks-infra-static"
  target      = "branch"
  enforcement = local.enforcement["required-checks-infra-static"]

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
      include = ["mindclade-internal-monorepo"]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      required_check {
        context = "infra-static"
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}
