<!-- mindclade-doc: runbook@1 -->

# Preserve the canonical monorepo state identity

> **Use when:** planning or verifying the historical repository-key migration from `mindclade`
> to `mindclade-internal-monorepo`.
> **Safety boundary:** these source blocks do not authorize a GitHub rename, state mutation, or
> Terraform apply.

The catalog's canonical source repository is `mindclade/mindclade-internal-monorepo`.
Terraform `moved` blocks preserve the state identity of the repository, access, environment,
custom-property, and Actions-variable resources that were historically keyed as `mindclade`.

Before planning, read the canonical repository through the GitHub API and record `nameWithOwner`,
immutable database ID, node ID, and default branch. Repository name alone is not sufficient
evidence of production authority.

1. Verify that the immutable ID for `mindclade-internal-monorepo` matches the repository ID
   already tracked in Terraform state.
2. Run the protected speculative plan against the exact reviewed revision. The `moved` blocks
   change Terraform addresses only; they do not invoke a GitHub rename.
3. If the IDs differ, stop. Use a separately reviewed state-adoption procedure; do not let a
   name-only Terraform plan choose between repositories.
4. Reject any plan that creates, deletes, or replaces the canonical repository, or retains a
   managed state address keyed as `mindclade` after migration.
5. After the protected apply, compare Terraform's `repository_ids` output to the preflight
   numeric ID and verify team grants, the `release` environment, custom properties, and Actions
   variables.

The compatibility blocks are inert when the old addresses are absent. Remove them only after an
approved state inventory proves every managed state completed the address migration and the
immutable repository-ID post-check passed.
