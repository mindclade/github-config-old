# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# GitOps uses merge queue, so every required context must run on both pull_request and
# merge_group. The production-handoff gate is stable for all changes: it is credential-free when
# production is staged/blocked and uses the protected production environment plus read-only WIF
# only when the proposed source is qualified-v1.
resource "github_organization_ruleset" "required_checks_gitops" {
  name        = "required-checks-gitops"
  target      = "branch"
  enforcement = local.enforcement["required-checks-gitops"]

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
      include = ["gitops"]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      required_check {
        context        = "contract"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "lint"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "schema"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "policy"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "exemptions"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "promotion-integrity"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "production-handoff-gate"
        integration_id = local.github_actions_integration_id
      }
      required_check {
        context        = "repository-invariants"
        integration_id = local.github_actions_integration_id
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}
