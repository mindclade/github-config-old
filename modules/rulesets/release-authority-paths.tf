# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

resource "github_organization_ruleset" "release_authority_paths" {
  name        = "release-authority-paths"
  target      = "branch"
  enforcement = local.enforcement["release-authority-paths"]

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
    repository_name {
      include = var.rulesets["release-authority-paths"].repositories
      exclude = []
    }
  }

  rules {
    pull_request {
      required_approving_review_count   = 2
      require_code_owner_review         = true
      dismiss_stale_reviews_on_push     = true
      required_review_thread_resolution = true
      require_last_push_approval        = true
      allowed_merge_methods             = ["squash"]

      required_reviewers {
        file_patterns = [
          ".github/workflows/release.yml",
          "ci/release/**",
        ]
        minimum_approvals = 1
        reviewer {
          id   = var.release_team_id
          type = "Team"
        }
      }

      required_reviewers {
        file_patterns = [
          ".github/workflows/release.yml",
          "ci/release/**",
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
