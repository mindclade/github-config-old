# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Required status checks for infrastructure-live. github-config has a dedicated ruleset because
# its path-aware workflow reports `plan / verdict`, while infrastructure-live reports `plan`.
#
# The plan check is the important one. Everything else here catches a class of mistake; the
# plan catches THIS mistake, on this PR, against real state — and it is the only check whose
# output a reviewer is expected to read rather than glance at.

resource "github_organization_ruleset" "required_checks_tf" {
  name        = "required-checks-tf"
  target      = "branch"
  enforcement = local.enforcement["required-checks-tf"]

  dynamic "bypass_actors" {
    for_each = local.bypass_incident_response
    content {
      actor_id    = bypass_actors.value.actor_id
      actor_type  = bypass_actors.value.actor_type
      bypass_mode = bypass_actors.value.bypass_mode
    }
  }

  # Scoped by repository NAME, not by `language = terraform`, and that is the whole lesson of
  # this file: a required-check context is coupled to how a repository STRUCTURES its CI, not
  # to what language it contains.
  #
  # infrastructure-live defines plan.yml with top-level jobs, so it reports bare contexts:
  # `fmt`, `validate`, `plan`.
  #
  # A repository using the terraform-module starter workflow instead CALLS
  # reusable-tf-plan.yml, and a called workflow reports as `<caller job id> / <called job id>`
  # — so it would report `plan / plan` and satisfy none of the checks below. Targeting by
  # language would sweep such a repo in here and block every merge in it.
  #
  # When the first template-based Terraform repo lands, give it its own ruleset with the
  # `<caller> / <called>` contexts rather than widening this one.
  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
    repository_name {
      include = ["infrastructure-live"]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      # These strings must equal the JOB IDS in infrastructure-live's plan workflow.
      # GitHub reports one check per job; a step produces nothing, so naming a step here
      # creates a check that is required and never satisfied — merges block forever with a
      # permanently pending status.
      #
      # Verify after any workflow edit:
      #   python3 -c "import yaml;print(sorted(yaml.safe_load(open('.github/workflows/plan.yml'))['jobs']))"
      required_check {
        context = "fmt"
      }

      required_check {
        context = "validate"
      }

      required_check {
        context = "plan"
      }

      # tflint and checkov exist only in github-config's workflow, not in
      # infrastructure-live's. A required check that a repo's workflow never produces blocks
      # that repo permanently, so these are declared in their own ruleset below, scoped by
      # repository name rather than by language.

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }

    # NO required_code_scanning HERE, deliberately.
    #
    # This ruleset targets github-config and infrastructure-live, and neither produces a
    # CodeQL result: between them they hold zero .go, .py, .js and .ts files, and
    # ruleset-workflows no longer injects reusable-codeql.yml into them for that reason.
    # Requiring a CodeQL result from a repository that generates none is a merge gate that
    # can never go green — and it reads, in a plan and in the UI, exactly like a gate that
    # is working.
    #
    # Its right home is required-checks-go, which targets the monorepo. Adding it there is
    # blocked on two things that must be observed rather than assumed: GHAS enabled on the
    # repository (see the header of the monorepo's security.yml) and one real CodeQL run
    # whose check context is confirmed. Until then this control is absent and said to be
    # absent, rather than present and inert.
  }
}

# ---------------------------------------------------------------------------------------
# Static analysis, scoped by repository NAME rather than by language property
# ---------------------------------------------------------------------------------------
# Still scoped by name rather than by `language = terraform`, for the reason given above: the
# context a repository reports depends on how its workflow is structured, not on what it
# contains.
#
# BOTH repositories are covered. This used to name github-config alone, on the premise that
# infrastructure-live holds no .tf files locally so tflint and checkov would analyse an empty
# directory. The premise is out of date: infrastructure-live's plan.yml defines both jobs
# (:101 and :131), each guarded by a `find . -name '*.tf'` probe that skips the tool and lets
# the JOB report success. The context is produced either way, so requiring it is safe — and
# the day that repository does vendor a module locally, the check is already in force rather
# than needing to be remembered.
resource "github_organization_ruleset" "required_checks_tf_static" {
  name        = "required-checks-tf-static"
  target      = "branch"
  enforcement = local.enforcement["required-checks-tf-static"]

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
      include = ["github-config", "infrastructure-live"]
      exclude = []
    }
  }

  rules {
    required_status_checks {
      required_check {
        context = "tflint"
      }

      required_check {
        context = "checkov"
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}

# ---------------------------------------------------------------------------------------
# Terraform tests, github-config only
# ---------------------------------------------------------------------------------------
# Its own ruleset because `test` is the one context that genuinely exists in one of these two
# repositories and not the other. github-config carries tests/access-model.tftest.hcl — 281
# lines asserting who can reach what, run by the `test` job in its plan.yml.
# infrastructure-live has no .tftest.hcl at all, so requiring `test` of it would block every
# merge there permanently.
#
# Without this, that suite was advisory: plan.yml's own header names `test` among the required
# checks, no ruleset required it, and a PR turning the access model red could merge with a red
# tick nobody had to explain. The file that says who can reach what is exactly the wrong file
# to leave ungated.
resource "github_organization_ruleset" "required_checks_tf_tests" {
  name        = "required-checks-tf-tests"
  target      = "branch"
  enforcement = local.enforcement["required-checks-tf-tests"]

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
      required_check {
        context = "test"
      }

      strict_required_status_checks_policy = true
      do_not_enforce_on_create             = true
    }
  }
}
