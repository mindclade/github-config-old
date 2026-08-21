# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Existing organization and repositories are adopted into Terraform state. These declarative
# imports are intentionally retained after adoption: they document resource provenance and are
# idempotent after the first successful apply.

import {
  to = module.organization.github_organization_settings.this
  id = "mindclade"
}

import {
  to = module.repositories.github_repository.this[".github"]
  id = ".github"
}

import {
  to = module.repositories.github_repository.this[".github-private"]
  id = ".github-private"
}

import {
  to = module.repositories.github_repository.this["github-config"]
  id = "github-config"
}

import {
  to = module.repositories.github_repository.this["bootstrap"]
  id = "bootstrap"
}

import {
  to = module.repositories.github_repository.this["infrastructure-live"]
  id = "infrastructure-live"
}

import {
  to = module.repositories.github_repository.this["gitops"]
  id = "gitops"
}

import {
  to = module.repositories.github_repository.this["mindclade-internal-monorepo"]
  id = "mindclade-internal-monorepo"
}

# Read-only GitHub API inventory on 2026-08-20 proved these bootstrap variables already exist.
# Import the exact intersection of live variables and the ARC-authority compiled catalog.
# Retired Buildkite authority values are absent from both live state and this import set.
# is enabled and its real UUID contract is available.
locals {
  preexisting_bootstrap_actions_variables = toset([
    "BILLING_ACCOUNT",
    "BREAK_GLASS_PRINCIPALS_JSON",
    "ENABLE_BUILDKITE_WIF",
    "GCP_ORG_ID",
    "GCP_REGION",
    "GH_ORGANIZATION",
    "GH_ORGANIZATION_ID",
    "GH_REPOSITORY_IDS_JSON",
    "RESOURCE_PREFIX",
    "SA_BOOTSTRAP_APPLY",
    "SA_BOOTSTRAP_DRIFT",
    "SA_BOOTSTRAP_PLAN",
    "SECURITY_CONTACT",
    "STATE_BUCKET_LOCATION",
    "STATE_KMS_LOCATION",
    "STATE_REPLICA_KMS_LOCATION",
    "STATE_REPLICA_LOCATION",
    "TFSTATE_BUCKET",
    "TFSTATE_REPLICA_BUCKET",
    "WIF_PROVIDER_APPLY",
    "WIF_PROVIDER_PLAN",
  ])

  preexisting_repository_environments = toset([
    "bootstrap:bootstrap",
    "bootstrap:bootstrap-recovery-read",
    "bootstrap:break-glass",
    "bootstrap:plan",
    "github-config:plan",
    "infrastructure-live:plan",
  ])
}

import {
  for_each = local.preexisting_bootstrap_actions_variables
  to       = module.repositories.github_actions_variable.this["bootstrap:${each.value}"]
  id       = "bootstrap:${each.value}"
}

import {
  for_each = local.preexisting_repository_environments
  to       = module.repositories.github_repository_environment.this[each.value]
  id       = each.value
}

# The 2026-08-20 read-only organization inventory resolved these immutable team IDs. Team
# descriptions and hierarchy still come from catalog/teams.yaml; the IDs only prevent Terraform
# from attempting to create duplicates during adoption. bootstrap-reviewers was not present and
# is intentionally excluded so Terraform may create that reviewed, IdP-backed team.
locals {
  preexisting_parent_teams = {
    biosecurity      = "19072991"
    engineering      = "19072990"
    incident-command = "19072982"
    release          = "19072993"
    security         = "19072983"
  }
  preexisting_child_teams = {
    data-platform  = "19073005"
    infrastructure = "19073003"
    model-serving  = "19073000"
    model-training = "19073004"
    platform       = "19073002"
    product        = "19072996"
    research       = "19072997"
  }
}

import {
  for_each = local.preexisting_parent_teams
  to       = module.teams.github_team.parent[each.key]
  id       = each.value
}

import {
  for_each = local.preexisting_child_teams
  to       = module.teams.github_team.child[each.key]
  id       = each.value
}

# Only these three rulesets were positively identified by immutable ID. The remaining desired
# rulesets stay behind the adoption gate until an organization-ruleset-capable credential proves
# whether each is absent or needs another import block.
import {
  to = module.rulesets.github_organization_ruleset.push_blocklist
  id = "21096509"
}

import {
  to = module.rulesets.github_organization_ruleset.tag_protection
  id = "21096168"
}

import {
  to = module.rulesets.github_repository_ruleset.merge_queue["mindclade-internal-monorepo"]
  id = "mindclade-internal-monorepo:21096177"
}
