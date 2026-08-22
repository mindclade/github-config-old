# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Restrict new release identities without weakening immutable existing identities. GitHub
# applies every matching ruleset, so Release may bypass this creation rule while the separate
# no-bypass tag-protection ruleset still rejects updates, deletion, and non-fast-forward moves.
resource "github_organization_ruleset" "release_tag_creation" {
  name        = "release-tag-creation"
  target      = "tag"
  enforcement = local.enforcement["release-tag-creation"]

  dynamic "bypass_actors" {
    for_each = local.bypass_release_tag_creation
    content {
      actor_id    = bypass_actors.value.actor_id
      actor_type  = bypass_actors.value.actor_type
      bypass_mode = bypass_actors.value.bypass_mode
    }
  }

  conditions {
    ref_name {
      include = ["refs/tags/v*"]
      exclude = []
    }
    repository_name {
      include = ["~ALL"]
      exclude = []
    }
  }

  rules {
    creation = true
  }
}
