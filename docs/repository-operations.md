<!-- mindclade-doc: reference@1 -->

# Repository estate operations

The `.github` repository owns the `Estate status` and `Ref janitor` workflow implementations.
This repository owns their GitHub App scopes, protected environments, and maintenance policy.

## Status dashboard

`mindclade-estate-observer` is selected to exactly the seven governed repositories. It has only
Actions, Checks, Contents, Metadata, and Pull Requests read permissions. Scheduled dashboard and
janitor-report jobs use the approval-free `repository-observability` environment, which is limited
to protected branches and contains the App ID plus protected private-key secret.

The dashboard records default-branch SHA and checks, latest workflow state, open pull requests,
extra remote branches, and tags. A failing default branch makes the workflow fail after the JSON
and Markdown reports are uploaded.

## Ref janitor

`catalog/repository-maintenance.json` is the sole deletion policy. It protects `main`, open pull
request heads, configured automation prefixes, semantic release tags, and every published GitHub
release. Unmerged branches are always preserved, even after retention, because unique commits are
potentially useful work and require human recovery review.

Scheduled runs only report. Deletion requires a manual dispatch from `.github` `main` with mode
`delete` and confirmation `DELETE`, a newly computed plan, Platform and Security approval in
`repository-maintenance`, its wait timer, and the separately scoped janitor App token.

## Activation and rollback

Create both Apps from `catalog/github-apps.yaml`, install them with selected repositories, place
only their App IDs in repository variables, and place private keys only in their named protected
environments. Run connected governance audit before enabling scheduled workflows.

To stop automation, disable the workflow and revoke or suspend the relevant App installation.
Restoring service requires correcting the catalog or secret and running a new report. Never widen
an App installation or bypass `repository-maintenance` to repair a failed deletion run.
