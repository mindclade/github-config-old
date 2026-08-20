# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Architecture

`catalog/` is the only human-authored policy source. The provider-free catalog module validates references and emits normalized values. Terraform modules compile those values into GitHub Enterprise repositories, custom properties, teams, access, environments, rulesets, Actions policy, and OIDC metadata.

Plan and drift use narrowly scoped short-lived GitHub App and Google Cloud identities. Mutation credentials are requested only by the apply job after the protected `governance` environment gate. No credential is stored in Terraform source, catalog files, tfvars, or saved plans.
