# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

terraform {
  # Bucket is created by the bootstrap repo. Partial configuration: the bucket name comes
  # from `-backend-config=backend.hcl` so this file carries no environment-specific value.
  #
  # Until bootstrap has been applied for the first time, this repo cannot initialise. That
  # ordering is deliberate and documented in bootstrap/docs/first-apply.md.
  backend "gcs" {
    prefix = "github-config"
  }
}
