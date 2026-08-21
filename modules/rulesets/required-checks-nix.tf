# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# The shared workflow always emits this verdict, including when an internal pull-request path
# check determines that no Nix-owned files changed. Resting enforcement remains evaluate until
# the immutable v4.1.0 release has produced native and rebuild evidence in every repository.
resource "github_organization_ruleset" "required_checks_nix" {
  name        = "required-checks-nix"
  target      = "branch"
  enforcement = local.enforcement["required-checks-nix"]

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
      include = [
        ".github",
        ".github-private",
        "bootstrap",
        "github-config",
        "gitops",
        "infrastructure-live",
        "mindclade-internal-monorepo",
      ]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      required_check {
        context = "nix / verdict"
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}
