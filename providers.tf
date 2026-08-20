# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# The workflow creates a short-lived GitHub App installation token and exports GITHUB_TOKEN.
# Keeping credentials outside Terraform variables prevents them from being serialized into a
# saved plan. GITHUB_OWNER is not required because owner is explicit here.
provider "github" {
  owner = var.organization

  write_delay_ms = 1000
  read_delay_ms  = 100
  max_retries    = 3
}
