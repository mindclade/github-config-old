# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

output "repositories" {
  description = "Managed repositories and the ids other repos need for WIF and ruleset bindings."
  value = {
    for name, r in github_repository.this : name => {
      repo_id    = r.repo_id
      node_id    = r.node_id
      visibility = r.visibility
      full_name  = r.full_name
      ssh_url    = r.ssh_clone_url
    }
  }
}

output "repository_ids" {
  description = "Repository name to numeric id."
  value       = { for name, r in github_repository.this : name => r.repo_id }
}

output "environments" {
  description = "Created environments and their gates, for the runbook and for audit."
  value = {
    for k, v in github_repository_environment.this : k => {
      repository  = v.repository
      environment = v.environment
      wait_timer  = v.wait_timer
    }
  }
}
