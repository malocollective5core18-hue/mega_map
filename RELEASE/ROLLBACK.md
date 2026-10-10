# Release Rollback and Recovery

This describes a safe owner-led recovery process. No Render service, production branch, or Supabase database was changed during this audit. Practice on staging first. Database rollback is not the same as application rollback; restoring a backup can discard writes made after its snapshot.

## Application rollback

1. Pause further release merges and record the failing Render deploy ID, commit SHA, time, logs, and affected endpoints without copying customer data into the incident report.
2. In Render, open the service’s **Events/Deploys** history and select **Rollback** for the last known-good deploy (or manually deploy its known-good commit). Verify health and customer/staff flows. This preserves branch history and avoids moving `production` backwards.
3. Open a `hotfix/<incident>` branch from `production`. Revert the faulty application change with a reviewed inverse commit or make a forward fix; merge by PR into protected `production` and also merge/cherry-pick the fix into `main` through review.
4. Tag the repaired release with the next appropriate semantic version only after gates pass. Record the incident and rollback in `CHANGELOG.md`/`READINESS.md`.

Example source-control preparation (replace placeholders only after the incident owner approves):

```sh
git fetch origin --tags
git switch -c hotfix/incident-short-name origin/production
# Make a reviewed forward fix, or use: git revert <faulty-commit-sha>
git status --short
git diff --check
git commit -am "Fix: <short incident description>"
git push -u origin hotfix/incident-short-name
```

To identify the commit behind a previous annotated tag without changing the current branch:

```sh
git fetch origin --tags
git rev-parse v1.0.0-rc1^{commit}
```

Use that SHA in Render's manual deploy screen only if the incident owner selects application rollback. Do not push an old tag to `production` or move a protected branch backwards; use the hotfix PR path above to reconcile source history.

Open PRs from that branch to `production` and `main` according to the branch rules. Do not use `reset --hard`, force push, or delete published tags/branches.

## Database migration recovery

- Prefer a forward-compatible corrective migration. Never run a destructive reverse migration against live customer data without a reviewed data-recovery plan and a verified backup.
- `python manage.py migrate --plan` shows pending operations; it does not prove a rollback is safe.
- Test both forward and any proposed reverse operation on a staging clone. Record schema/data consequences and owner approval before production execution.
- If data corruption or destructive migration occurred, stop writes if operationally safe, preserve logs, and restore to a **new** Supabase project/instance first. Validate its schema, data point-in-time, application connectivity, and privacy controls before any cutover.

## Supabase restore procedure (owner-operated)

1. Confirm the project is on a plan/tier with the required backup or point-in-time recovery entitlement. The free tier does not provide routine automatic backup coverage according to `DEPLOY.md`.
2. In the Supabase dashboard, open the project’s **Database → Backups** (or the current point-in-time recovery control), choose a restore timestamp before the incident, and restore to a new project where the plan supports it. Do not overwrite the only source project during the drill.
3. Record the chosen UTC timestamp and restore job result. Validate migrations, representative records, access policies, extensions, and application health without exposing customer values in tickets/logs.
4. Only after approval, update the Render `DATABASE_URL` secret to the verified restored database connection, restart/redeploy the service, and check health/read-only behavior. Keep the previous database isolated until the incident owner authorizes disposal.
5. Document lost writes, reconciliation, and notification obligations. For a privacy/security incident, follow the approved response and legal process.

Exact Supabase controls vary by plan and may change. The owner must confirm the dashboard procedure and recovery-point objective with Supabase before relying on it; this audit did not access or alter a live project.
