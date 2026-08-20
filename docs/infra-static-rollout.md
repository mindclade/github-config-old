# `infra-static` ruleset rollout

`required-checks-infra-static` is intentionally checked in with `enforcement: evaluate`. It
targets only `mindclade/mindclade-internal-monorepo`, requires the exact `infra-static` check
context, uses strict merge-result evaluation, and does not enforce on branch creation.

Before changing the catalog to `active`:

1. Confirm the existing repository's immutable numeric ID matches the adoption inventory and
   that the plan imports it at the canonical address rather than creating or replacing it.
2. Merge the `pull_request` and `merge_group` workflow changes without activating this ruleset.
3. Observe successful `infra-static` check runs for at least one ordinary pull request and one
   merge-queue group. Record the run URLs and exact head SHAs in the change request.
4. Run a disposable pull request that makes the static validator fail and confirm the same
   `infra-static` context concludes `failure` rather than disappearing or being skipped.
5. Review the Terraform plan. It must update only this evaluate-mode ruleset to active; it must
   not replace a repository or another ruleset.
6. Apply through the protected `governance` environment and confirm the ruleset targets only
   repository `mindclade-internal-monorepo` through the GitHub UI/API.
