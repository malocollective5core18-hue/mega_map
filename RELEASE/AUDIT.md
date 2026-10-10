# Repository and Release Audit

**Audit date:** 10 October 2026
**Audited revision:** `26f328cd9201cc2d1765de9510eaa67dfec0b16d` (`main`)
**Release decision:** Not ready for a production branch or release tag.

## Repository state

| Check | Result | Evidence |
|---|---|---|
| Current branch | Pass | `main` |
| `main` vs `origin/main` | Pass | Both point at `26f328c`; no ahead/behind commits reported. |
| Tracked working tree | Pass | No tracked modifications at audit start. |
| Whole working tree | Fail | `SRS.md` is untracked and therefore is not present in the audited Git revision. Preserve and add it through the normal reviewed change before cutting a release. |
| Existing branches | Fail | Only `main` and `origin/main` exist; there is no `production` branch or release tag. |
| Recent history | Pass | Three commits, newest first: cleanup (`26f328c`), Render/Supabase preparation (`1070513`), initial secure setup (`662b889`). |

The checkout at the audited revision equals `origin/main`. Do not treat the untracked SRS as part of that commit.

## Secret and sensitive-data scan

`gitleaks` and `trufflehog` are not installed in this environment. A targeted scan of all three reachable commits searched for private-key headers, common AWS/GitHub token forms, and credential-like assignments. It found only three test-user password literals (`safe-test-password`) in `core/tests.py`; these are test fixtures, not credentials for an external service. A working-tree scan found documented placeholder values in `.env.example` and variable names/usages in code and documentation. No real credential or customer-data finding was identified by these checks.

**Limitation:** this fallback scan is not equivalent to a maintained secret scanner. Run Gitleaks (including full history) in CI or on a trusted workstation before the first production release. If a real credential is found in any reachable history, stop release work and rotate it; do not rewrite published history here.

## Ignore rules and tracked contents

`.gitignore` covers `.env` files (while allowing `.env.example`), virtual environments, `.local-deps`, bytecode/cache directories, local SQLite/database files, collected static output, media, SQL/dump files, keys, secrets directories, and common Python coverage/tool caches. The checked `.local-deps`, `.env`, and `.venv` examples are ignored as intended.

The ignore file does not explicitly cover `.vscode/`, `.idea/`, or general editor swap files. Add those if the team wants editor-local configuration excluded. No IDE files, agent prompts, internal AI instructions, database dumps, private keys, media, or large generated dependency trees are tracked in the 47-file baseline. The largest tracked files are `index.html` (~56 KiB) and `templates/staff/dashboard.html` (~48 KiB); none is unusually large for this application.

The Render blueprint currently points at `main`, auto-deploys, and selects the free plan. It is not configured to deploy from a protected production branch, and free hosting is limited to demo or controlled-pilot use under `DEPLOY.md`.

## Release inputs

- `SRS.md` exists in the working tree but is not committed at this revision.
- `ARCHITECTURE.md`, `API.md`, `ASSUMPTIONS.md`, `STAFF-GUIDE.md`, `DEPLOY.md`, and `TEST-REPORT.md` were reviewed as release inputs.
- No `CHANGELOG.md` or `RELEASE/` artifacts existed at audit start.
- `requirements.txt` uses lower/upper bounds, not exact pins; there is no lock file or hash-locked dependency set.

## Audit commands and outcomes

| Command/check | Result |
|---|---|
| `git status --short --branch` | `main...origin/main`; `SRS.md` untracked |
| `git branch -avv` | Only `main` and `origin/main` |
| `git log --oneline --decorate -20` | Three commits; current equals stated cleanup commit |
| `git rev-parse HEAD` and `git rev-parse origin/main` | Identical SHA |
| Targeted current tree/history secret-pattern scan | No real credential found; test placeholder literals only; scanner unavailable |
| `git check-ignore` on local env/dependency examples | Ignored as expected |
