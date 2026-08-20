# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Real-time governance events only.
#
# This is NOT the audit-log path. GitHub Enterprise Cloud streams the audit log natively to
# a GCS bucket — configured in the enterprise UI, provisioned by infrastructure-live, and
# tracked in docs/enterprise-manual-controls.md. That stream is complete, ordered, and
# retried; a webhook is none of those things and will silently drop events during an
# outage. Using a webhook as the audit trail produces a log that looks complete and is not.
#
# What a webhook is good for is latency: knowing within seconds that someone disabled a
# ruleset, rather than at the next nightly drift run.

resource "github_organization_webhook" "governance_events" {
  count = var.webhook_url != "" ? 1 : 0

  active = true

  configuration {
    url          = var.webhook_url
    content_type = "json"
    insecure_ssl = false
    secret       = var.webhook_secret
  }

  events = [
    # The events that indicate a control was changed outside Terraform.
    "repository_ruleset",
    "organization",
    "member",
    "membership",
    "team",
    "team_add",
    "repository",
    "repository_vulnerability_alert",

    # Security signal worth acting on before the next scheduled scan.
    "secret_scanning_alert",
    "secret_scanning_alert_location",
    "code_scanning_alert",
    "security_advisory",

    # Deployment gate decisions — who approved what, and when.
    "deployment_protection_rule",
    "deployment_review",
  ]
}
