<!-- mindclade-doc: reference@1 -->

# GitHub App authority contracts

`catalog/control-plane-apps.yaml` is the machine-readable registration and installation
contract for Terraform plan and apply identities. `catalog/github-apps.yaml` is the equivalent
contract for ARC runner registration, GitOps promotion, production-qualification source reads,
release-governance evidence reads, estate observation, protected ref cleanup, and workflow-pin pull
requests. Neither catalog proves an App exists:
`scripts/audit-connected-governance.py` must observe the exact installation, permission map, and
selected repositories before production activation.

## Control-plane Apps

Both Apps use selected-repository installation and cover exactly the seven managed repositories.
Webhooks and event subscriptions are disabled.

The plan App has repository read permissions for administration, Actions, Actions variables,
environments, metadata, repository custom properties, and vulnerability alerts; organization read
permissions for members, Actions variables, custom properties, and self-hosted runners; and
`organization_administration: write`. That final permission is an unavoidable GitHub API exception:
the organization-ruleset GET endpoint requires organization Administration write. The token is
therefore **not** token-level read-only. Its private key belongs only to the protected `plan`
environment, and workflow validation plus a negative authorization test must prove the plan path
does not issue a mutating request.

The apply App has write access only to the surfaces Terraform owns: repository administration,
Actions and Actions variables, environments, repository custom properties, vulnerability alerts,
organization members, organization administration, organization Actions variables, organization
custom-property definitions, and self-hosted runners. Metadata remains read-only. Its private key
belongs only to the protected `governance` environment.

The exact variable/secret names are in the catalog. Do not store either PEM in Terraform state,
repository files, plan artifacts, command lines, or logs.

The production-qualification App is installed on exactly the seven managed repositories, has no
organization permissions or webhooks, and receives only Actions read, Contents read, and Metadata
read. Its private key is stored in the infrastructure-owned Secret Manager container and is
available only to the protected GitOps production-qualification reader identity.

The release-governance reader App is selected only to `.github` and
`mindclade-internal-monorepo`. It has repository Administration, Actions, Contents, and Metadata
read plus organization Members read, with no write permission, webhook, or event subscription.
Those reads let protected release workflows verify repository settings, immutable-release and
workflow evidence, exact source objects, and approver membership without using the workflow's
repository-scoped `GITHUB_TOKEN` as organization authority.

Terraform manages the non-secret `RELEASE_GOVERNANCE_READER_APP_ID` Actions variable in both
selected repositories from one operator environment input. Terraform must never receive
`RELEASE_GOVERNANCE_READER_APP_PRIVATE_KEY`: store that value only as an Actions secret. The
`.github` release-governance caller expects a repository secret because authorization precedes its
protected publication environments; the monorepo publisher expects the same-named secret only in
its protected `terraform-module-release` environment. Never commit, log, artifact, export through
`CI_VARIABLES`, or place either private-key copy in a Terraform variable, plan, or state file.

The estate-observer App is read-only and selected to the same exact estate. The ref-janitor App
adds only Contents write, plus Metadata and Pull Requests read, and is usable for deletion only
through the reviewed `repository-maintenance` environment. See
[`repository-operations.md`](repository-operations.md) for retention, deletion, and rollback.

The workflow-pin-updater App is selected only to `.github-private` and `github-config`. It has
Contents write, Pull Requests write, and Metadata read, with no organization permission or webhook.
Its key is available only through the protected `governance` environment. The automation may open
draft review PRs; it cannot merge them or push to `main`. Both pin upgrades and DR activation fail
closed until the machine adoption graph and fresh connected-evidence ledger qualify every gate.

## Qualification

1. Create each App from the exact catalog contract and install it with selected repositories.
2. Record its immutable App and installation IDs outside Git, then set only the declared App-ID
   variable and the documented protected or repository PEM secret.
   For the release-governance reader, use the exact repository/protected-environment secret
   placements above and verify both selected repositories receive the same App ID.
3. Run `make connected-audit` with an organization-owner read credential capable of listing other
   installations and their selected repositories. An App installation token cannot use the
   `/user/installations/{id}/repositories` evidence endpoint for another App; an authorization
   failure is a failed audit, not permission to skip the check.
4. Run the plan App's positive read/plan test and negative mutation test. Exercise a harmless
   rejected mutation against a disposable qualification repository, never a production setting.
5. Change the catalog-managed `GOVERNANCE_CONNECTED_DRIFT` variable from `false` to `true` only
   after the plan App ID and protected PEM are present. The scheduled workflow fails closed if
   activation is requested with either credential missing.
6. Run the apply App only through a reviewed, checksummed saved plan waiting at `governance`.
7. For the workflow-pin-updater App, run the blocked preparation commands first, then qualify v5
   and its connected evidence before allowing either protected PR-preparation workflow to proceed.

## Rotation and rollback

Generate a second private key, update the protected secret, run the connected audit and plan, then
revoke the old key. To stop an incident, revoke or suspend the installation and cancel queued
governance runs. Restore service by correcting the catalog or credential and re-running a new plan;
never reuse a saved plan created before the revocation or broaden permissions to make a check pass.
Rotate both release-governance reader secret copies before revoking its previous key, and fail
closed if either repository cannot mint and exercise a read-only installation token.
