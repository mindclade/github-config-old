# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

locals {
  legal_policy_file_patterns = [
    "LICENSE",
    "LEGAL.md",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".github/CODEOWNERS",
    ".github/MINDCLADE_PROPRIETARY_SOURCE_HEADER.txt",
    ".github/workflows/publish-policy-bundle.yml",
    ".github/workflows/reusable-oci-build.yml",
    ".github/workflows/synchronize-policy-bundle.yml",
    "actions/validate-repository-home/validate.py",
    "scripts/validate-repository-home.py",
    "scripts/generate-third-party-notices.py",
    "scripts/enrich-spdx-license.py",
    "scripts/validate_security_txt.py",
    "tools/policy_bundle.py",
    "tools/enrich_spdx_license.py",
    "tools/third_party_notices.py",
    "contracts/policy-bundle/**",
    "contracts/security-txt.json",
    "contracts/third-party-materials.json",
    "**/.well-known/security.txt",
    "docs/policy-bundle.md",
    "catalog/teams.yaml",
    "catalog/access.yaml",
    "catalog/github-apps.yaml",
    "catalog/rulesets.yaml",
    "idp/mappings.yaml",
    "scripts/export-idp-groups.py",
    "modules/rulesets/**",
  ]
}

resource "github_organization_ruleset" "legal_policy_paths" {
  name        = "legal-policy-paths"
  target      = "branch"
  enforcement = local.enforcement["legal-policy-paths"]

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
    repository_name {
      include = sort(keys(var.repositories))
      exclude = []
    }
  }

  rules {
    pull_request {
      # The numeric floor prevents one person who belongs to multiple teams from satisfying the
      # functional reviewer blocks alone. IdP governance must additionally keep these approval
      # populations independently staffed before connected activation.
      required_approving_review_count   = 3
      require_code_owner_review         = true
      dismiss_stale_reviews_on_push     = true
      required_review_thread_resolution = true
      require_last_push_approval        = true
      allowed_merge_methods             = ["squash"]

      required_reviewers {
        file_patterns     = local.legal_policy_file_patterns
        minimum_approvals = 1
        reviewer {
          id   = var.legal_team_id
          type = "Team"
        }
      }

      required_reviewers {
        file_patterns     = local.legal_policy_file_patterns
        minimum_approvals = 1
        reviewer {
          id   = var.security_team_id
          type = "Team"
        }
      }

      required_reviewers {
        file_patterns     = local.legal_policy_file_patterns
        minimum_approvals = 1
        reviewer {
          id   = var.platform_team_id
          type = "Team"
        }
      }
    }
  }
}
