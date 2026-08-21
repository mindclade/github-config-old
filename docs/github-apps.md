<!-- mindclade-doc: reference@1 -->

# GitHub App authority contracts

`catalog/control-plane-apps.yaml` is the machine-readable registration and installation
contract for Terraform plan and apply identities. `catalog/github-apps.yaml` is the equivalent
contract for ARC runner registration and GitOps promotion. Neither catalog proves an App exists:
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

## Qualification

1. Create each App from the exact catalog contract and install it with selected repositories.
2. Record its immutable App and installation IDs outside Git, then set only the declared App-ID
   variable and protected-environment PEM secret.
3. Run `make connected-audit` with an organization-owner read credential capable of listing other
   installations and their selected repositories. An App installation token cannot use the
   `/user/installations/{id}/repositories` evidence endpoint for another App; an authorization
   failure is a failed audit, not permission to skip the check.
4. Run the plan App's positive read/plan test and negative mutation test. Exercise a harmless
   rejected mutation against a disposable qualification repository, never a production setting.
5. Run the apply App only through a reviewed, checksummed saved plan waiting at `governance`.

## Rotation and rollback

Generate a second private key, update the protected secret, run the connected audit and plan, then
revoke the old key. To stop an incident, revoke or suspend the installation and cancel queued
governance runs. Restore service by correcting the catalog or credential and re-running a new plan;
never reuse a saved plan created before the revocation or broaden permissions to make a check pass.
