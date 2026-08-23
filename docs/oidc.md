# GitHub Actions OIDC governance

GitHub Actions authenticates to Google Cloud through bootstrap-managed Workload
Identity Federation. No service-account JSON keys are permitted.

## Subject policy

`catalog/oidc-policy.yaml` is authoritative. The organization template records a possible
future custom format, but every managed repository is explicitly kept on GitHub's default
subject (`use_default = true`). Mindclade also requires GitHub's immutable default-subject mode.
Protected plan and release bindings use this environment form:

```text
repo:OWNER@OWNER-ID/REPO@REPO-ID:environment:ENVIRONMENT-NAME
```

According to GitHub's [immutable subject claims documentation](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims),
repositories created after July 15, 2026 receive immutable default subjects automatically.
Older repositories must be opted in through GitHub's OIDC settings or REST API before any
bootstrap WIF binding is activated. Resetting a repository to `use_default = true` removes a
custom claim template; it is not accepted as evidence that a pre-cutover repository has been
opted into immutable defaults.

The pinned GitHub provider does not expose the REST API's `use_immutable_subject` field.
Terraform continues to own the organization claim template and repository `use_default` flags;
`scripts/enforce-immutable-oidc.py` is the deliberately narrow adapter for the missing field.
Speculative plan and drift run it read-only. The exact post-merge apply sets the field only after
Terraform succeeds, then re-reads the organization and every catalog repository and verifies an
ID-bearing `sub_claim_prefix`. Removing that adapter while the provider gap exists is a trust
regression.

The dormant custom template contains only claims available to every workflow job:

```text
repository_owner_id
repository_id
repository
workflow_ref
ref
```

`environment` and `job_workflow_ref` are intentionally not mandatory subject
claims. `environment` exists only for jobs that reference a GitHub environment,
and `job_workflow_ref` exists only for called reusable workflows. Requiring them
organization-wide would break plan, validation, and direct workflow jobs.

## Cloud trust

Google Cloud trust must require the exact immutable default `sub`, immutable organization ID,
repository ID, expected repository, explicit audience, and an allowed workflow and ref. Apply
service accounts are bound to the exact `apply.yml` workflow on `refs/heads/main`. The apply job
itself references a protected GitHub environment, so it cannot start or request its token before
that environment gate is passed.

Default subjects preserve environment identity. Separately mapped immutable repository IDs,
workflow/ref claims, explicit audiences, and provider conditions supply defense in depth.

## Bazel cache trust

Bootstrap contract `1.5.0` defines a dedicated `gh-bazel-cache` provider for
`mindclade-internal-monorepo`; it is not a broader repository provider. Its exact route contract
allows pull-request merge refs to use only the cache reader and allows only protected-main pushes,
merge-group refs for main, and the main-branch nightly schedule to use the cache writer. Manual
dispatch, feature branches, tags, alternate workflows, and substituted immutable IDs remain
outside the contract.

`github-config` publishes the route JSON to `infrastructure-live` as a bootstrap-derived source
input. It publishes `WIF_PROVIDER_BAZEL_CACHE`, `SA_BAZEL_CACHE_READER`, and
`SA_BAZEL_CACHE_WRITER` to the monorepo only from exact applied handoff `1.4.0`, after checking the
provider byte-for-byte and the distinct common-CI account names. Those variables alone do not
activate a cache client or prove connected token exchange; endpoint publication and positive and
negative route qualification remain separate protected steps.

## Workstation image trust

Bootstrap contract `1.6.0` defines `gh-workstation-image` for the internal monorepo's exact
`nixos-image.yml@refs/heads/main` caller, immutable owner/repository IDs, manual dispatch, the
protected `workstation-image-publication` environment, and
`reusable-nixos-gce-image-publish.yml@refs/tags/v5.0.0`. The mapped `workstation-image:` subject
cannot cross into release or cache bindings.

Governance publishes the provider, dedicated `workstation-image-pub` account, and exact source
bucket only from applied infrastructure handoff `1.5.0`. These non-secret variables cannot mint a
token outside the provider condition and do not grant Compute Image creation authority.

`idp-sync.yml` has two explicit cloud-authentication paths. Internal pull requests use the
protected `plan` environment subject. Schedule and main-branch dispatch runs use the exact
`idp-sync.yml@refs/heads/main` workflow identity bootstrap allowlists, with no environment, so a
nightly offboarding check cannot stall behind an interactive approval.

## Change sequence

Changing the subject template is a trust migration:

1. record every immutable owner and repository ID from an authoritative GitHub response;
2. enable immutable default subjects for any repository that predates the GitHub cutover;
3. make the bootstrap WIF mapping/conditions accept the exact intended immutable subjects;
4. verify plan and apply token exchange in a non-production path;
5. change `repository_opt_in` only after a reviewed credentialed plan proves every subject;
6. apply this repository's subject-template change;
7. verify every control repository can authenticate and a wrong repository ID is denied;
8. remove obsolete compatibility conditions.

Never change both sides blindly in one unrecoverable step.

## What counts as token-exchange evidence

Step 4 above is satisfied only by an immutable Actions run that proves the exchange end to end.
The cloud authentication action can configure an external-account credential file lazily, so a
green authentication step alone is not proof that a token was minted.

- Positive evidence must consume a cloud API with the federated credential (for example, an
  actual access-token request or an authenticated Terraform backend initialization) from the
  exact ref and environment under test.
- Negative evidence must attempt to mint or use a token from a non-allowlisted subject and record
  the cloud provider's denial; a run that only configures credentials proves nothing.
- Cite the retained run URLs and the exact commit SHA. Temporary probe branches may be deleted
  once the run record exists, and no IAM binding, protected environment, provider condition, or
  default-branch source may be changed to obtain evidence.
