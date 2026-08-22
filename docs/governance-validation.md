<!-- mindclade-doc: architecture@1 -->

# Governance contract validation

`scripts/validate-catalog.py` validates policy data and implementation behavior without GitHub or
cloud credentials. Catalog YAML and JSON are schema-checked. Security-sensitive Terraform is
parsed as HCL and inspected by resource, block, attribute, and expression identity; a matching
word in a comment or unrelated resource cannot satisfy the check.

The semantic Terraform checks cover required-status-check rulesets, tag creation and immutable
tag protection, adoption imports, the complete-or-empty environment project handoff, and managed
repository OIDC defaults. The nightly access-expiry contract is checked from parsed workflow YAML
by job and step identity. `tests/test_governance_contracts.py` includes intentional mutations that
retain the old text in comments while changing behavior, and proves those mutations fail.

## Promotion contract

`required-checks-mixed` and `required-checks-infra-static` accept only `evaluate` or `active`.
They may become active only when their exact activation gates in
`catalog/governance-activation.yaml` are qualified. The current catalog remains in `evaluate`;
source validation does not constitute connected evidence or permission to apply governance.

## Deferred cost verdict

`catalog/required-check-readiness.yaml` records the candidate `infracost / verdict` context and
keeps it out of `required-checks-tf` until connected evidence proves that the source contract
reports correctly. The follow-up is exact:

1. Merge the source workflow that emits one stable, always-present verdict on both
   `pull_request` and `merge_group` without granting the verdict mutation credentials.
2. Observe successful and intentional-negative results for that exact context on both event types.
3. Record the observed events, negative evidence, qualified context, and gate in the readiness and
   activation contracts.
4. Add only that context to `required-checks-tf`, review the exact protected plan, and apply through
   the governance environment.

Until all four steps are complete, cost analysis remains advisory and the active Terraform
ruleset continues to require only `fmt`, `validate`, and `plan`.

## Remaining textual checks

Some checks intentionally remain content-oriented: the solo-founder and adoption runbooks must
retain exact operational warnings, the branch-protection discovery record must retain its reviewed
incident facts, and the CI-variable exporter retains legacy source-token guards in addition to its
behavioral unit tests. These are not used to infer a Terraform resource shape or ruleset context.
