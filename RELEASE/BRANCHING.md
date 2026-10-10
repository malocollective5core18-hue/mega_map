# Branching and Release Model

## Intended model

- `main` is the development integration branch. Changes arrive through short-lived pull requests.
- `production` is reserved for commits that passed the release gates. No direct commits, force pushes, or deletion.
- `feature/<short-name>` and `fix/<short-name>` branch from `main` and merge back through review.
- `hotfix/<short-name>` branches from `production`; after review and release, the fix must also be merged into `main`.
- Release candidates and releases use annotated semantic-version tags, for example `v1.0.0-rc1` followed by `v1.0.0`.

## Current state and decision

At audit time, only `main` exists and points to `26f328c`. It matches `origin/main`. There is no `production` branch or release tag. `SRS.md` is also untracked.

**Do not create `production` yet.** The dependency-install, production Django, PostgreSQL, security, and SRS acceptance gates have not all passed. Creating a release-candidate branch now would invite deployment from a revision that is known to lack release evidence. Once all blockers in `READINESS.md` are resolved on a reviewed commit, create `production` from that exact passing commit and protect it before enabling deployment.

## Owner setup after gates pass

From a clean checkout of the approved release commit:

```sh
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c production
git push -u origin production
git tag -a v1.0.0-rc1 -m "Mauzosheet controlled-pilot release candidate 1"
git push origin v1.0.0-rc1
```

Use these commands only after the release gates pass and the SRS is included in the reviewed commit. Subsequent `production` updates must come from reviewed PRs whose head is an already tested `main` commit or a reviewed production hotfix. Never force-push or delete the branch.

After the reviewed PR is merged into `production`, create/push a final version tag on that approved commit:

```sh
git switch production
git pull --ff-only origin production
git tag -a v1.0.0 -m "Mauzosheet v1.0.0"
git push origin v1.0.0
```

## GitHub branch protection

In **Repository → Settings → Branches → Add branch protection rule** (or the equivalent ruleset screen), apply the following to `production`:

1. Require a pull request before merging.
2. Require at least one approval from a person other than the author.
3. Dismiss stale approvals when new commits are pushed; require approval of the latest push.
4. Require all release CI checks to pass before merge (dependency audit, Django checks, PostgreSQL tests, frontend syntax/security checks, and secret scan).
5. Require branches to be up to date before merging.
6. Block force pushes and branch deletion.
7. Restrict bypass privileges to named repository owners only; do not grant routine bypass.

Create equivalent review/check requirements on `main` if the team wants the stated PR-only development model enforced. Require a release PR checklist and link its evidence to `RELEASE/READINESS.md`.

## Render branch setting

The checked-in `render.yaml` currently uses `branch: main`, `plan: free`, and `autoDeploy: true`. After a paid service and production branch are approved, the owner must change the Render service's deploy branch to `production`, confirm environment variables and database, and ensure only reviewed production commits trigger deploys. Do not change or deploy live hosting as part of this audit.

The owner deploys through the Render dashboard: open the service, confirm the selected branch is `production`, and use **Manual Deploy → Deploy latest commit** after the release PR and gates pass. Confirm the deployed SHA equals the approved/tagged SHA. The current `build.sh` runs `collectstatic`, `migrate --noinput`, cache-table creation, and role setup during build. For a controlled manual migration from a trusted environment with production environment variables already loaded, the commands are:

```sh
python manage.py migrate --plan
python manage.py migrate --noinput
```

Do not run those commands against a live database until a backup and migration review are complete. Do not use local development settings for the production migration.
