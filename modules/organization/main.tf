# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
resource "github_organization_settings" "this" {
  billing_email = var.billing_email
  name          = "Mindclade"
  description   = "Frontier models for programmable biology."
  blog          = "https://mindclade.com"
  email         = "engineering@mindclade.com"

  # Nobody gets anything by being a member. Access is granted per repository in
  # locals.team_access and nowhere else. This single line is what makes that map the
  # complete access model rather than an addition to an invisible baseline.
  default_repository_permission = "none"

  # Repository creation is a Terraform change, not a button. An undeclared repo inherits no
  # rulesets, has no CODEOWNERS, and is invisible to drift detection — it is the one way to
  # get an ungoverned surface inside a governed org.
  members_can_create_repositories          = false
  members_can_create_public_repositories   = false
  members_can_create_private_repositories  = false
  members_can_create_internal_repositories = false

  # A private fork leaves the org's ruleset and secret-scanning perimeter while keeping the
  # code. There is no workflow here that needs it.
  members_can_fork_private_repositories = false

  members_can_create_pages         = false
  members_can_create_public_pages  = false
  members_can_create_private_pages = false

  has_organization_projects = true
  has_repository_projects   = false

  # Security defaults for every new repository. These are "on by default" switches, not
  # retroactive: turning them on here does not enable them on repos that already exist.
  # repository_properties.tf and the rulesets cover the existing set.
  advanced_security_enabled_for_new_repositories = true
  # Keep vulnerability intelligence enabled even though Renovate, rather than Dependabot,
  # owns dependency-update pull requests. Alerts and automatic update PRs are separate controls.
  dependabot_alerts_enabled_for_new_repositories               = true
  dependabot_security_updates_enabled_for_new_repositories     = false
  dependency_graph_enabled_for_new_repositories                = true
  secret_scanning_enabled_for_new_repositories                 = true
  secret_scanning_push_protection_enabled_for_new_repositories = true

  # Commits made through the web UI are signed off automatically; the signed-commit rule in
  # the baseline ruleset would otherwise make web edits impossible.
  web_commit_signoff_required = true
}

# ---------------------------------------------------------------------------------------
# NOT MANAGEABLE HERE
# ---------------------------------------------------------------------------------------
# SAML SSO enforcement, SCIM provisioning, and IdP-driven team sync have no resource in the
# GitHub Terraform provider at any version. They are configured in the enterprise UI and
# tracked against the checklist in docs/enterprise-manual-controls.md, which drift.yml
# prompts a human to walk monthly. Writing them here as a comment rather than leaving the
# gap silent is the point: an uncoded control that nobody knows is uncoded is the failure.
