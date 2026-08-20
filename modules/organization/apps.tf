# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# GitHub App installations and their repository scope.
#
# The App itself — its permissions, its private key, its webhook — is created in the GitHub
# UI and cannot be declared in Terraform. What IS declarable, and what matters most, is which
# repositories each installation can reach. An App installed on "all repositories" has the
# union of its permissions across the whole org; scoping it here is the difference between a
# compromised App key being a bad day and being an extinction event.
#
# Installation ids come from: gh api /orgs/Mindclade/installations --jq '.installations[] | {id, app_slug}'

data "github_organization_app_installations" "this" {}

locals {
  # Keyed by app slug so the config reads by name rather than by opaque id.
  installations = {
    for i in data.github_organization_app_installations.this.installations :
    i.app_slug => i
  }

  # Only scope Apps that are actually installed. Referencing an absent one would fail the
  # plan on a map lookup, which is a confusing way to learn an App was uninstalled.
  installed_app_scopes = {
    for slug, repos in var.app_scopes : slug => repos
    if contains(keys(local.installations), slug)
  }
}

resource "github_app_installation_repositories" "this" {
  for_each = local.installed_app_scopes

  # The data source returns id as a number; the resource wants a string.
  installation_id       = tostring(local.installations[each.key].id)
  selected_repositories = each.value
}

# Surfaces the gap rather than failing on it: an App listed in app_scopes but not installed
# is usually a rename or a removal, and it should be visible in the plan output.
check "declared_apps_are_installed" {
  assert {
    condition     = length(local.installed_app_scopes) == length(var.app_scopes)
    error_message = "An App in var.app_scopes is not installed on this organization. Install it, or remove it from app_scopes. Check: gh api /orgs/${var.organization}/installations"
  }
}

output "app_installations" {
  description = "Apps installed on the org, and whether this config scopes them."
  value = {
    for slug, i in local.installations : slug => {
      installation_id = i.id
      managed_here    = contains(keys(var.app_scopes), slug)
    }
  }
}
