# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# The floor. Applies to the default branch of every repository in the organization.
#
# Nothing here is negotiable per-repo: a repository that needs looser rules than this does
# not belong in the org. Stricter rules are layered on top by the other rulesets.

resource "github_organization_ruleset" "baseline_all" {
  name        = "baseline-all"
  target      = "branch"
  enforcement = local.enforcement["baseline-all"]

  # No bypass. If the baseline is blocking something legitimate, fix the baseline in a PR —
  # a bypass here would silently apply to every repository at once.
  dynamic "bypass_actors" {
    for_each = local.bypass_none
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
      include = ["~ALL"]
      exclude = []
    }
  }

  rules {
    # Branch lifecycle: main cannot be deleted, and history cannot be rewritten. non_fast_forward
    # blocks force-push, which is the one that turns "someone made a mistake" into
    # "the history someone else reviewed no longer exists".
    deletion         = true
    non_fast_forward = true

    # Direct pushes to main are blocked by requiring a pull request, below. `creation` and
    # `update` are left unset deliberately: setting them blocks branch creation entirely.

    required_linear_history = true
    required_signatures     = true

    pull_request {
      required_approving_review_count = 1

      # A new push invalidates prior approvals. Without this, "approved" means "approved at
      # some earlier state of this branch", which is not the same claim.
      dismiss_stale_reviews_on_push = true

      # Unresolved review comments block the merge. Resolving is one click; the alternative
      # is threads that quietly scroll out of view.
      required_review_thread_resolution = true

      # The author cannot approve their own final push. Combined with the count above, this
      # is what makes "one approval" mean one other person.
      require_last_push_approval = true

      require_code_owner_review = false

      allowed_merge_methods = ["squash"]
    }
  }
}
