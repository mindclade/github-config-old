# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Required status checks for polyglot repositories, selected by `mindclade_language_profile = mixed`.
#
# WHY THIS EXISTS. required-checks-go requires exactly two contexts — "ci / build" and
# "codeql / analyze (go)". A `mixed` repository also runs a Python lane and a Rust lane, and
# neither was required by anything, so a pull request could go red in both and still merge.
#
# That is not hypothetical. mindclade commit d74b978 ("refactor(training): migrate distributed
# package layout") took the Python scaffold ratchet in tests/integration/test_python_scaffold.py
# from 193 placeholders to 225 without moving SCAFFOLD_BASELINE, and merged. Every pull request
# afterwards inherited a red Python lane it did not cause. No admin bypass was involved and no
# rule was broken: the check simply was not required. A ratchet that can be merged red has
# stopped being a ratchet.
#
# SCOPED TO `mixed` ONLY, deliberately. The `language` property also allows "python" and
# "rust", but no repository carries either value today, and required-checks-go's own header
# records what happens when you require a context nothing emits: a permanently pending status
# that blocks merges forever. Extend the property_values list in the change that gives a
# repository one of those languages, not in anticipation of it.

resource "github_organization_ruleset" "required_checks_mixed" {
  name        = "required-checks-mixed"
  target      = "branch"
  enforcement = local.enforcement["required-checks-mixed"]

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
    repository_property {
      include = [
        {
          name            = "mindclade_language_profile"
          property_values = ["mixed"]
          source          = "custom"
        }
      ]
    }
  }

  rules {
    required_status_checks {
      # "<caller job id> / <called job id>", as for the Go check. Both reusable-uv-ci and
      # reusable-rust-ci name their job `build`, so the caller's job id is what distinguishes
      # them: mindclade's presubmit.yml calls them from jobs `python` and `rust`.
      required_check {
        context = "python / build"
      }

      required_check {
        context = "rust / build"
      }

      # A plain job in the caller, so the context is the job's own name. This is the lane that
      # runs the repository's architecture invariants — dependency layering, component
      # maturity, Cargo/Bazel parity.
      #
      # The header on locals.tf already claimed required-checks-go enforced this. It never
      # did; that ruleset requires "ci / build" and "codeql / analyze (go)". The claim is
      # true from here on.
      required_check {
        context = "architecture"
      }

      # This stable caller-job name qualifies the real PostgreSQL registry and admission
      # adapters, including transaction failure injection and concurrent no-overspend pressure.
      # Keep the ruleset in evaluate mode until the context is observed on pull_request and
      # merge_group runs and an intentional failure proves enforcement.
      required_check {
        context = "Go registry + admission / live PostgreSQL and failure injection"
      }

      # The monorepo emits this exact stable caller-job name on pull_request and merge_group.
      # Ordinary pull requests use Bazel-authoritative affected selection; merge-group runs
      # execute the full configured graph before the queue may merge the change. Keep this
      # ruleset in evaluate until both event shapes and an intentional failure are observed.
      required_check {
        context = "bazel / verdict"
      }

      # Re-run checks against the merge result, not the branch head. Without this, two PRs
      # that each pass alone can merge into a broken main.
      strict_required_status_checks_policy = true

      # A branch created and immediately opened as a PR has no check runs yet; enforcing on
      # create just adds a retry loop.
      do_not_enforce_on_create = true
    }
  }
}
