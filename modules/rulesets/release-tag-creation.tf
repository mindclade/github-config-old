# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Stage a restriction on new release identities without weakening immutable existing identities.
# GitHub applies every matching ruleset, so Release may bypass this creation rule after its
# separate activation gate is qualified while the no-bypass tag-protection ruleset continues to
# reject updates, deletion, and non-fast-forward moves.
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

  lifecycle {
    precondition {
      condition = (
        local.enforcement["release-tag-creation"] != "active" ||
        (
          var.release_tag_creation_control_qualified &&
          local.enforcement["tag-protection"] == "active"
        )
      )
      error_message = "release-tag-creation cannot become active before its connected qualification gate is qualified and no-bypass tag-protection is active."
    }
  }
}
