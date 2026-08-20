# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Mandatory workflows are defined in the `.github` repository and enforced here. The workflow
# implementation and the enforcement mechanism intentionally have different owners.
resource "github_organization_ruleset" "ruleset_workflows" {
  name        = "ruleset-workflows"
  target      = "branch"
  enforcement = local.enforcement["ruleset-workflows"]

  dynamic "bypass_actors" {
    for_each = local.bypass_security
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
          name            = "mindclade_repository_class"
          property_values = var.rulesets["ruleset-workflows"].classes
          source          = "custom"
        }
      ]
    }
  }

  rules {
    required_workflows {
      required_workflow {
        repository_id = var.dot_github_repo_id
        path          = ".github/workflows/required-repository-policy.yml"
        ref           = var.rulesets["ruleset-workflows"].workflow_ref
      }

      required_workflow {
        repository_id = var.dot_github_repo_id
        path          = ".github/workflows/required-security-baseline.yml"
        ref           = var.rulesets["ruleset-workflows"].workflow_ref
      }

      do_not_enforce_on_create = true
    }
  }
}
