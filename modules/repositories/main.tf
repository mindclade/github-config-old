# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

resource "github_repository" "this" {
  # checkov:skip=CKV_GIT_1: Repositories here are `internal`, which checkov does not model.
  #
  # CKV_GIT_1 asserts `visibility == "private"`. Repositories in this catalog are private or internal — readable by the enterprise, invisible outside it — and that is a decision
  # catalog/repositories.yaml records at length, not an oversight.
  #
  # Internal is not weaker than private here; it is what makes the reusable workflows in
  # .github callable across the enterprise, which is the mechanism most of this governance
  # runs on. Making them private would break every `uses:` in the estate.
  #
  # This skip matters operationally: `checkov` is a REQUIRED status check for this repository
  # (modules/rulesets/required-checks-tf.tf) and runs with soft_fail: false, so without it
  # every merge in github-config blocks on a finding that is working as intended.
  for_each = var.repositories

  name        = each.key
  description = each.value.description
  visibility  = each.value.visibility
  topics      = each.value.topics

  has_issues      = each.value.has_issues
  has_projects    = each.value.has_projects
  has_wiki        = false
  has_discussions = each.key == ".github"
  archived        = each.value.lifecycle == "archive"

  # Squash only. Merge commits make `git log --first-parent` unreadable and rebase merges
  # break the signed-commit rule, because rewriting a commit invalidates its signature.
  allow_merge_commit     = false
  allow_squash_merge     = true
  allow_rebase_merge     = false
  allow_auto_merge       = true
  allow_update_branch    = true
  delete_branch_on_merge = true

  squash_merge_commit_title   = "PR_TITLE"
  squash_merge_commit_message = "PR_BODY"

  # Forking a private repo moves the code outside every ruleset and scanning control that
  # applies here, so it is off even on the public repo, where a fork is a PR away anyway.
  allow_forking = false

  web_commit_signoff_required = true

  # Setting auto_init on an import is a no-op, while a genuinely new repository needs an
  # initial `main` branch before github_branch_default can manage it. The provider ignores
  # this creation-only field after adoption.
  auto_init = true

  security_and_analysis {
    # Private and internal repositories, which supports GHAS. The guard remains because
    # advanced_security cannot be set on a PUBLIC repository — GitHub enables it there
    # unconditionally and rejects an explicit value — and this is the line that would
    # otherwise fail the apply if one were ever flipped public.
    dynamic "advanced_security" {
      for_each = each.value.visibility == "public" ? [] : [1]
      content {
        status = "enabled"
      }
    }
    secret_scanning {
      status = "enabled"
    }
    secret_scanning_push_protection {
      status = "enabled"
    }
  }

  lifecycle {
    # Terraform will happily delete a repository to resolve a diff it cannot apply in place
    # — a visibility change is the usual trigger. There is no undo.
    prevent_destroy = true

    ignore_changes = [
      # Written by GitHub when a repo is created from a template, and meaningless afterwards.
      template,
      # auto_init only matters at creation; it drifts to false and would otherwise show a
      # permanent diff on every plan.
      auto_init,
    ]
  }
}

# Default branches are catalog policy, not an implicit provider default.
resource "github_branch_default" "this" {
  for_each = var.repositories

  repository = github_repository.this[each.key].name
  branch     = each.value.default_branch
}

# Split out of github_repository, where the inline attribute is deprecated.
# Vulnerability alerts remain enabled. Renovate owns dependency-update pull requests, but
# disabling the advisory signal would remove an independent security control.
resource "github_repository_vulnerability_alerts" "this" {
  for_each = var.repositories

  repository = github_repository.this[each.key].name
  enabled    = true
}

# Every repository must carry its own community health files.
#
# This check exists because .github is INTERNAL rather than public (see catalog/repositories.yaml), which
# means org-wide inheritance of CONTRIBUTING.md, SECURITY.md, and issue templates does not
# happen. Without inheritance there is no safety net: a repository with no SECURITY.md
# simply has no disclosure policy, and nothing surfaces that.
#
# Terraform cannot see repository contents, so this cannot be enforced here. drift.yml
# checks it via the API instead. This block documents the requirement at the point where
# someone changing visibility would read it.
check "community_health_files_are_per_repo" {
  assert {
    condition     = github_repository.this[".github"].visibility == "internal"
    error_message = "The .github repository is intentionally internal; every repository must retain its own SECURITY.md and CONTRIBUTING.md."
  }
}
