# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Rejects the push itself, before anything reaches a branch.
#
# This is categorically different from a required check. A check runs after the commit is on
# a branch, by which point a leaked key is already in the reflog, in every fetch, and in the
# events API. A push ruleset means the object never lands.
#
# target = "push" is only available on private and internal repositories owned by an
# organization on Enterprise Cloud. Every repo here is internal, so all of them are covered —
# ~ALL with no exclusions. If one is ever made public, exclude it by name here or the ruleset
# will fail to apply against it.

locals {
  push_blocked_extensions = [
    # GitHub's ruleset API requires extension patterns, including the literal `*.` prefix.
    "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore", "*.asc", "*.ppk",
    "*.tfstate", "*.tfstate.backup",
    "*.kubeconfig", "*.netrc",
  ]
}

resource "github_organization_ruleset" "push_blocklist" {
  name        = "push-blocklist"
  target      = "push"
  enforcement = local.enforcement["push-blocklist"]

  # No bypass. Every legitimate case for committing one of these has a better answer:
  # Secret Manager for keys, Git LFS for large files, remote state for tfstate.
  dynamic "bypass_actors" {
    for_each = local.bypass_none
    content {
      actor_id    = bypass_actors.value.actor_id
      actor_type  = bypass_actors.value.actor_type
      bypass_mode = bypass_actors.value.bypass_mode
    }
  }

  conditions {
    # No ref_name on a push ruleset: it applies to every ref, which is the intent. A key
    # pushed to a feature branch is exactly as leaked as one pushed to main.
    repository_name {
      include = ["~ALL"]
      exclude = []
    }
  }

  rules {
    file_extension_restriction {
      restricted_file_extensions = local.push_blocked_extensions
    }

    file_path_restriction {
      restricted_file_paths = [
        "**/credentials.json",
        "**/service-account*.json",
        "**/*service_account*.json",
        "**/.env",
        "**/.env.*",
        "**/id_rsa",
        "**/id_ed25519",
        "**/.npmrc",
        "**/.pypirc",
        "**/terraform.tfvars",
        "**/*.auto.tfvars",
        "**/.terraform/**",
        "**/kubeconfig",
        "**/.kube/config",
      ]
    }

    # Megabytes, not bytes — the provider accepts 1-100 and rejects anything else. Model
    # weights, datasets, and checkpoints belong in GCS; a repo that has accreted a few
    # hundred of these takes ten minutes to clone, forever afterwards.
    max_file_size {
      max_file_size = 50
    }

    # Windows caps paths at 260 characters by default, and a deeply nested Bazel output tree
    # will exceed it. Cheaper to reject the path than to debug a checkout that half-worked.
    max_file_path_length {
      max_file_path_length = 255
    }
  }
}

check "push_blocked_extensions_are_api_patterns" {
  assert {
    condition     = alltrue([for extension in local.push_blocked_extensions : startswith(extension, "*.")])
    error_message = "Every push-blocked extension must use GitHub's required *.extension pattern."
  }
}
