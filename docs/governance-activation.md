<!-- mindclade-doc: runbook@1 -->

# Governance activation preflight

> **Use when:** moving the staged source changes into live GitHub enforcement.
> **Safety boundary:** source qualification is not authority to publish, approve, apply, or bypass.

`catalog/governance-activation.yaml` is the machine gate for this rollout. It stays `blocked`
until every named item has connected evidence. The current solo-founder exception does not cover
release publication, protected-environment approval, governance apply, repository administration,
or retrospective closeout.

## Current resting source state

- `baseline-all` and `protected-paths` remain the active desired floor with no baseline bypass and
  two approvals plus CODEOWNERS on enterprise/production control repositories.
- `ruleset-workflows` remains `evaluate` while the referenced `v5.0.0` tag is absent.
- `release-tag-creation` blocks new `v*` tags for everyone except the Release team, while the
  separate no-bypass `tag-protection` ruleset prevents Release from moving or deleting them.
- `required-checks-bootstrap` expects `plan / verdict` but remains `evaluate` until both its
  connected-plan and credential-free paths are observed.
- `required-checks-nix` remains `evaluate` until all seven repositories have native and rebuild
  evidence from the published v5 workflow.
- `.github` declares the two protected workflow-release environments, but the connected inventory
  found neither environment live.

## Required order

1. Add a qualified person independent of both same-human founder accounts to the applicable
   Platform or Security review function. Preserve distinct people across the two v5 publication
   approvals.
2. Refresh organization-ruleset and Terraform-state inventory with an organization-ruleset-capable
   plan identity. Import every known-existing address and reject delete/replace actions.
   Remove redundant `.github` repository ruleset `21082865` only after the organization
   `tag-protection` rule is independently proven active and no-bypass.
3. Review the exact merged-SHA Terraform plan. Its first bounded apply may reconcile
   `baseline-all` and `protected-paths` and create `workflow-release-platform` and
   `workflow-release-security`; it must leave release-dependent rules in evaluate mode.
4. Merge the canonical `.github` v5 source through independent review. A Release-team operator—not
   an agent—creates the annotated `v5.0.0` tag on that exact merged commit through the active
   creation guard. Qualify the exact tag, approve
   both protected environments with distinct people, and publish the immutable release.
5. Adopt the published release and policy provenance record through consumer pull requests. Keep
   legacy Nix checks until `nix / verdict` is observed on pull requests, merge groups, schedules,
   all native platforms, and both rebuilds.
6. Merge the bootstrap plan workflow and observe `plan / verdict` for both a relevant Terraform
   change and an unaffected documentation change. Confirm a close event cancels a stale waiting
   run without cloud authentication.
7. Update the gate evidence to `qualified`, run the exact merged-SHA plan, and only then promote
   `ruleset-workflows`, `required-checks-bootstrap`, and `required-checks-nix` to active in a
   separate reviewed change.
8. Complete the independent retrospective for
   [bootstrap PR #25](https://github.com/mindclade/github-config/issues/33).

## Stop conditions

Stop on a missing tag or release, same-human environment approvals, absent workflow context,
unimported live object, Terraform deletion/replacement, administrator bypass, incomplete API
scope, or disagreement between the plan, state list, connected audit, and activation record.
