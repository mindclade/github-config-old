# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Organization-level Actions policy compiled from catalog/actions-policy.yaml. The
# enterprise policy ceiling is reviewed separately through docs/enterprise-manual-controls.md;
# whichever layer is narrower is the effective policy.

resource "github_actions_organization_permissions" "this" {
  enabled_repositories = var.actions_policy.enabled_repositories
  allowed_actions      = var.actions_policy.allowed_actions

  # The single highest-value line in this file. GitHub rejects any `uses:` that names a tag
  # or branch instead of a full commit SHA, org-wide, at run time. A tag is mutable: an
  # attacker who compromises an action repository can repoint v4 at their own code and every
  # workflow in the org picks it up on the next run with no diff anywhere.
  #
  # This turns SHA-pinning from a convention people follow into one they cannot skip.
  sha_pinning_required = var.actions_policy.sha_pinning_required

  allowed_actions_config {
    # Restrict by explicit allow-list only. We already enforce SHA pinning globally,
    # so these entries are both the governance boundary and the execution surface.
    github_owned_allowed = var.actions_policy.github_owned_allowed

    verified_allowed = var.actions_policy.verified_creator_allowed

    # Everything else must be named. The allowlist is authored once in the catalog and
    # compiled into this resource; modules contain no hidden action policy.
    patterns_allowed = var.actions_policy.allowed_action_patterns
  }
}

resource "github_actions_organization_workflow_permissions" "this" {
  organization_slug = var.organization

  # Read-only GITHUB_TOKEN by default. A workflow that needs to write says so in its own
  # `permissions:` block, which makes the grant visible in review rather than ambient.
  default_workflow_permissions = var.actions_policy.default_workflow_permissions

  # A workflow approving a pull request is a workflow bypassing the review requirement.
  can_approve_pull_request_reviews = var.actions_policy.can_approve_pull_request_reviews
}
