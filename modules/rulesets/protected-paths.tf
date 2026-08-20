# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Stricter merge requirements on the repositories that govern the estate, and stricter still
# on the paths within them that are expensive to get wrong.
#
# Targets by custom property, not by name. A new foundation-repository class repo inherits this the moment
# its `repository class` property is set, with no edit here — which is the point of the property existing.

resource "github_organization_ruleset" "protected_paths" {
  name        = "protected-paths"
  target      = "branch"
  enforcement = local.enforcement["protected-paths"]

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
          property_values = var.rulesets["protected-paths"].classes
          source          = "custom"
        }
      ]
    }
  }

  rules {
    pull_request {
      # Two approvals across the board on these repositories, plus code-owner review.
      required_approving_review_count   = 2
      require_code_owner_review         = true
      dismiss_stale_reviews_on_push     = true
      required_review_thread_resolution = true
      require_last_push_approval        = true
      allowed_merge_methods             = ["squash"]

      # Path-scoped reviewers, layered on top. required_approving_review_count above is the
      # floor for the whole PR; these raise it further for PRs that touch specific paths, and
      # name WHO must approve rather than just how many.
      required_reviewers {
        file_patterns     = ["rendered/production/**"]
        minimum_approvals = 2
        reviewer {
          id   = var.platform_team_id
          type = "Team"
        }
      }

      required_reviewers {
        # `modules/rulesets/**`, not `rulesets/**`. The rulesets moved under modules/ and this
        # pattern did not follow, so security review on the files that define every merge
        # requirement in the org had silently stopped matching anything. A path pattern that
        # matches nothing is invisible: the ruleset applies, the reviewer requirement is
        # configured, and no PR ever triggers it.
        #
        # `**/rulesets/**` rather than the exact path so a future move does not repeat this.
        file_patterns     = ["policy/**", "**/rulesets/**", "**/binary-authorization/**"]
        minimum_approvals = 1
        reviewer {
          id   = var.security_team_id
          type = "Team"
        }
      }

      required_reviewers {
        # Terraform anywhere in these repos changes real infrastructure.
        file_patterns     = ["**/*.tf", "**/*.hcl"]
        minimum_approvals = 1
        reviewer {
          id   = var.infrastructure_team_id
          type = "Team"
        }
      }

      required_reviewers {
        # Identity, trust, privileged workflow, and public-visibility controls are security
        # changes even when the implementation language is Terraform or YAML.
        file_patterns = [
          "**/identity/**",
          "**/wif*",
          "**/oidc*",
          "**/kms*/**",
          "**/binary-authorization/**",
          "**/.github/workflows/apply.yml",
          "**/.github/workflows/recovery-drill.yml",
          "catalog/access*.yaml",
          "catalog/actions-policy.yaml",
          "catalog/oidc-policy.yaml",
          "catalog/repositories.yaml",
        ]
        minimum_approvals = 1
        reviewer {
          id   = var.security_team_id
          type = "Team"
        }
      }
    }
  }
}
