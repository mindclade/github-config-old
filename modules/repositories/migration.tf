# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# State-address compatibility for the GitHub repository rename. These blocks are inert when
# the old addresses are absent. They must remain until every managed state has applied the
# rename and the numeric repository-ID post-check in docs/repository-rename.md has passed.
moved {
  from = github_repository.this["mindclade"]
  to   = github_repository.this["mindclade-internal-monorepo"]
}

moved {
  from = github_branch_default.this["mindclade"]
  to   = github_branch_default.this["mindclade-internal-monorepo"]
}

moved {
  from = github_repository_vulnerability_alerts.this["mindclade"]
  to   = github_repository_vulnerability_alerts.this["mindclade-internal-monorepo"]
}

moved {
  from = github_team_repository.this["mindclade:engineering"]
  to   = github_team_repository.this["mindclade-internal-monorepo:engineering"]
}

moved {
  from = github_team_repository.this["mindclade:platform"]
  to   = github_team_repository.this["mindclade-internal-monorepo:platform"]
}

moved {
  from = github_team_repository.this["mindclade:security"]
  to   = github_team_repository.this["mindclade-internal-monorepo:security"]
}

moved {
  from = github_team_repository.this["mindclade:release"]
  to   = github_team_repository.this["mindclade-internal-monorepo:release"]
}

moved {
  from = github_repository_environment.this["mindclade:release"]
  to   = github_repository_environment.this["mindclade-internal-monorepo:release"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_repository_class"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_repository_class"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_owner_team"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_owner_team"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_criticality"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_criticality"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_data_classification"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_data_classification"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_production_authority"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_production_authority"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_ci_profile"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_ci_profile"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_language_profile"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_language_profile"]
}

moved {
  from = github_repository_custom_property.this["mindclade:mindclade_lifecycle"]
  to   = github_repository_custom_property.this["mindclade-internal-monorepo:mindclade_lifecycle"]
}

moved {
  from = github_actions_variable.this["mindclade:ARTIFACT_REGISTRY_HOST"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:ARTIFACT_REGISTRY_HOST"]
}

moved {
  from = github_actions_variable.this["mindclade:DEV_PLATFORM_PROJECT_ID"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:DEV_PLATFORM_PROJECT_ID"]
}

moved {
  from = github_actions_variable.this["mindclade:STAGING_PLATFORM_PROJECT_ID"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:STAGING_PLATFORM_PROJECT_ID"]
}

moved {
  from = github_actions_variable.this["mindclade:PRODUCTION_PLATFORM_PROJECT_ID"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:PRODUCTION_PLATFORM_PROJECT_ID"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_BUILD_ATTESTOR_PROJECT"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_BUILD_ATTESTOR_PROJECT"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_BUILD_ATTESTOR"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_BUILD_ATTESTOR"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_QUALIFICATION_ATTESTOR"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_QUALIFICATION_ATTESTOR"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_DEPLOYMENT_ATTESTOR"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_DEPLOYMENT_ATTESTOR"]
}

moved {
  from = github_actions_variable.this["mindclade:BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION"]
}

moved {
  from = github_actions_variable.this["mindclade:SA_ARTIFACT_SIGNER"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:SA_ARTIFACT_SIGNER"]
}

moved {
  from = github_actions_variable.this["mindclade:WIF_PROVIDER_SIGNER"]
  to   = github_actions_variable.this["mindclade-internal-monorepo:WIF_PROVIDER_SIGNER"]
}
