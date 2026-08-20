# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Provider-free contract tests for the human-authored catalog.
variables {
  catalog_path = "catalog"
}

run "estate_matches_the_blueprint" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = toset(keys(output.repositories)) == toset([
      ".github", ".github-private", "github-config", "bootstrap", "infrastructure-live", "gitops", "mindclade-internal-monorepo"
    ])
    error_message = "The repository catalog must contain exactly the seven blueprint repositories."
  }
}

run "repository_classes_and_visibility_are_explicit" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = alltrue([
      for _, repository in output.repositories :
      contains(keys(output.repository_classes), repository.repository_class)
    ])
    error_message = "A repository uses an undeclared repository_class."
  }

  assert {
    condition = alltrue([
      output.repositories[".github"].visibility == "internal",
      output.repositories[".github-private"].visibility == "private",
      output.repositories["github-config"].visibility == "private",
      output.repositories["bootstrap"].visibility == "private",
      output.repositories["infrastructure-live"].visibility == "private",
      output.repositories["gitops"].visibility == "internal",
      output.repositories["mindclade-internal-monorepo"].visibility == "internal",
    ])
    error_message = "Repository visibility differs from the enterprise platform blueprint."
  }

  assert {
    condition = alltrue([
      for _, repository in output.repositories : repository.visibility != "public"
    ])
    error_message = "Public visibility requires a separate security, IP, licensing, and secret-history review."
  }
}

run "production_authority_is_narrow" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = alltrue([
      for _, repository in output.repositories :
      repository.production_authority == "false" || contains(
        ["enterprise-control", "production-control"],
        repository.repository_class,
      )
    ])
    error_message = "Only enterprise-control or production-control repositories may hold production authority."
  }

  assert {
    condition = (
      output.repositories["bootstrap"].repository_class == "enterprise-control" &&
      output.repositories["bootstrap"].data_classification == "restricted"
    )
    error_message = "bootstrap must remain restricted enterprise-control infrastructure."
  }
}

run "access_is_team_based_and_non_admin" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = alltrue(flatten([
      for _, grants in output.team_access : [
        for _, permission in grants : contains(["pull", "triage", "push", "maintain"], permission)
      ]
    ]))
    error_message = "Catalog access grants may not use admin or unknown permissions."
  }

  assert {
    condition = alltrue(flatten([
      for _, grants in output.team_access : [
        for team, _ in grants : contains(keys(output.teams), team)
      ]
    ]))
    error_message = "access.yaml references an undeclared team."
  }

  assert {
    condition     = !contains(keys(output.team_access["bootstrap"]), "engineering")
    error_message = "The broad engineering team must not receive bootstrap access."
  }
}

run "critical_owners_are_correct" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = (
      output.repositories["github-config"].owner_team == "security" &&
      output.team_access["github-config"]["security"] == "maintain"
    )
    error_message = "Security must own and maintain github-config."
  }

  assert {
    condition = (
      output.repositories["bootstrap"].owner_team == "infrastructure" &&
      output.repositories["gitops"].owner_team == "platform"
    )
    error_message = "Control repository ownership differs from the blueprint."
  }
}

run "team_hierarchy_and_restricted_teams_are_safe" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = alltrue([
      for _, team in output.teams :
      try(team.parent, null) == null ? true : try(output.teams[team.parent].parent, null) == null
    ])
    error_message = "Team hierarchy may be at most two levels deep."
  }

  assert {
    condition = (
      output.teams["biosecurity"].privacy == "secret" &&
      output.teams["incident-command"].privacy == "secret"
    )
    error_message = "Biosecurity and incident-command membership must remain secret."
  }
}

run "deployment_gates_match_risk" {
  command = plan
  module { source = "./modules/catalog" }

  assert {
    condition = (
      length(output.environments["production"].reviewer_teams) >= 2 &&
      output.environments["production"].wait_timer >= 10 &&
      output.environments["production"].prevent_self_review &&
      output.environments["production"].protected_branches
    )
    error_message = "Production requires two reviewing teams, a delay, no self-review, and protected branches."
  }

  assert {
    condition = (
      output.environments["governance"].prevent_self_review &&
      output.environments["bootstrap"].prevent_self_review &&
      output.environments["bootstrap-recovery-read"].prevent_self_review &&
      output.environments["break-glass"].prevent_self_review
    )
    error_message = "Critical control-plane environments must prevent self-review."
  }

  assert {
    condition = (
      contains(output.repositories["bootstrap"].environments, "plan") &&
      contains(output.repositories["github-config"].environments, "plan") &&
      contains(output.repositories["infrastructure-live"].environments, "plan") &&
      contains(output.environments["plan"].reviewer_teams, "infrastructure") &&
      output.environments["plan"].prevent_self_review &&
      !output.environments["plan"].protected_branches &&
      !output.environments["plan"].custom_branch_policies
    )
    error_message = "Infrastructure plans require a review-gated environment that permits pull-request merge refs."
  }

  assert {
    condition = (
      contains(output.repositories["bootstrap"].environments, "bootstrap-recovery-read") &&
      contains(output.environments["bootstrap-recovery-read"].reviewer_teams, "infrastructure") &&
      contains(output.environments["bootstrap-recovery-read"].reviewer_teams, "security") &&
      output.environments["bootstrap-recovery-read"].prevent_self_review &&
      output.environments["bootstrap-recovery-read"].protected_branches &&
      !output.environments["bootstrap-recovery-read"].custom_branch_policies
    )
    error_message = "Bootstrap state inspection requires its dedicated governed recovery-read environment."
  }

  assert {
    condition = (
      contains(output.repositories["gitops"].environments, "staging") &&
      contains(output.repositories["gitops"].environments, "production") &&
      output.environments["staging"].protected_branches &&
      !output.environments["staging"].custom_branch_policies &&
      output.environments["staging"].prevent_self_review &&
      contains(output.environments["staging"].reviewer_teams, "platform") &&
      output.environments["production"].protected_branches &&
      !output.environments["production"].custom_branch_policies &&
      output.environments["production"].prevent_self_review &&
      contains(output.environments["production"].reviewer_teams, "platform") &&
      contains(output.environments["production"].reviewer_teams, "security")
    )
    error_message = "GitOps staging and production promotions require protected branches, independent review, and explicit production security approval."
  }
}
