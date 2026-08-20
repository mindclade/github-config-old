# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Enterprise-scoped reference configuration.
#
# This module is intentionally not instantiated by the organization root. See README.md and
# docs/enterprise-manual-controls.md. It may be adopted only as a separate state and protected
# enterprise-credential workflow after existing objects are imported and recovery is tested.

data "github_enterprise" "this" {
  slug = var.enterprise_slug
}

# Actions policy at the enterprise level. This is the ceiling; policies/actions.tf sets the
# org-level policy underneath it. A pattern allowed here but not there is still blocked —
# the narrower of the two always wins, which is why both exist.
resource "github_enterprise_actions_permissions" "this" {

  enterprise_slug       = var.enterprise_slug
  enabled_organizations = "all"
  allowed_actions       = "selected"

  allowed_actions_config {
    github_owned_allowed = false
    verified_allowed     = false

    # Every pattern is pinned to an exact version. GitHub matches these against the `uses:`
    # string, so `owner/repo@sha` is permitted by `owner/repo@*` but the SHA-pinning
    # requirement below is what actually forces the SHA.
    patterns_allowed = var.allowed_action_patterns
  }
}

resource "github_enterprise_actions_workflow_permissions" "this" {

  enterprise_slug                  = var.enterprise_slug
  default_workflow_permissions     = "read"
  can_approve_pull_request_reviews = false
}

# GitHub Advanced Security defaults, enterprise-wide. Distinct from the org-level flags in
# org.tf: this covers organizations added to the enterprise later, which would otherwise
# arrive with scanning off.
resource "github_enterprise_security_analysis_settings" "this" {

  enterprise_slug                                              = var.enterprise_slug
  advanced_security_enabled_for_new_repositories               = true
  secret_scanning_enabled_for_new_repositories                 = true
  secret_scanning_push_protection_enabled_for_new_repositories = true
  secret_scanning_validity_checks_enabled                      = true
  secret_scanning_push_protection_custom_link                  = var.secret_scanning_link
}

# The organization as the enterprise sees it. Import this rather than create it — the org
# already exists, and a create would fail on a name collision at best.
resource "github_enterprise_organization" "this" {

  enterprise_id = data.github_enterprise.this.id
  name          = var.organization
  display_name  = "Mindclade"
  description   = "Primary engineering organization."
  billing_email = var.billing_email
  admin_logins  = var.enterprise_admin_logins

  lifecycle {
    # Removing the last admin locks everyone out of the organization with no in-band way
    # back. Terraform cannot tell an intentional handover from a typo, so it refuses both.
    precondition {
      condition     = length(var.enterprise_admin_logins) >= 2
      error_message = "enterprise_admin_logins needs at least two logins: one admin is a single point of failure for org recovery."
    }
  }
}
