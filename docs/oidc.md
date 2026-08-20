# GitHub Actions OIDC governance

GitHub Actions authenticates to Google Cloud through bootstrap-managed Workload
Identity Federation. No service-account JSON keys are permitted.

## Subject policy

`catalog/oidc-policy.yaml` is authoritative. The organization template and every
managed repository are configured from the same catalog value.

The subject uses only claims available to every workflow job:

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

Google Cloud trust must independently require the immutable organization ID and
repository ID, expected repository, explicit audience, and an allowed workflow
and ref. Apply service accounts are bound to the exact `apply.yml` workflow on
`refs/heads/main`. The apply job itself references a protected GitHub environment,
so it cannot start or request its token before that environment gate is passed.

The subject is useful for audit and defense in depth; mapped immutable claims are
the authorization source of truth.

## Change sequence

Changing the subject template is a trust migration:

1. make the bootstrap WIF mapping/conditions accept the intended claims;
2. verify plan and apply token exchange in a non-production path;
3. apply this repository's subject-template change;
4. verify every control repository can authenticate;
5. remove obsolete compatibility conditions.

Never change both sides blindly in one unrecoverable step.
