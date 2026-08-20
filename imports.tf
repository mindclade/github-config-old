# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Existing organization and repositories are adopted into Terraform state. These declarative
# imports are intentionally retained after adoption: they document resource provenance and are
# idempotent after the first successful apply.

import {
  to = module.organization.github_organization_settings.this
  id = "Mindclade"
}

import {
  to = module.repositories.github_repository.this[".github"]
  id = ".github"
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
