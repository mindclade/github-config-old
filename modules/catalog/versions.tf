# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

terraform {
  # No required_providers block, deliberately, and it is the defining property of this module:
  # it declares no resources and needs no provider, which is what lets tests/access-model.tftest.hcl
  # run offline with no credentials.
  #
  # Adding a provider here would quietly remove that.
  required_version = ">= 1.15.0, < 1.16.0"
}
