# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Release tags are immutable.
#
# This exists because of one specific failure: infrastructure-live pins modules to semver
# tags. If a `v1.4.0` tag can be moved, then "pinned to a tag" provides exactly as much
# protection as tracking a branch, while looking like it provides more. Everything downstream
# that reasons about a pinned version — every plan, every audit, every rollback — depends on
# the tag meaning one commit forever.
#
# The same applies to container images referenced by tag, which is why the delivery path uses
# digests instead.

resource "github_organization_ruleset" "tag_protection" {
  name        = "tag-protection"
  target      = "tag"
  enforcement = local.enforcement["tag-protection"]

  # Deliberately empty even for security. A moved release tag is not recoverable by moving it
  # back: anything that already resolved the old one has the old bytes. Cut v1.4.1 instead.
  dynamic "bypass_actors" {
    for_each = local.bypass_none
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
    # update = true blocks moving an existing tag. deletion = true blocks deleting and
    # recreating it, which is the obvious way around the first rule.
    update           = true
    deletion         = true
    non_fast_forward = true

    tag_name_pattern {
      name     = "stable-semver-only"
      operator = "regex"
      pattern  = "^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$"
    }
  }
}
