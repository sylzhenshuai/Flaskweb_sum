# alt_web01 Agent Guidelines

## Scope

- These rules apply to `src/` and its Python, templates, and static assets.
- Preserve unrelated user changes. Never reset, clean, overwrite, or force-push them.
- Prefer the smallest change that preserves the existing Flask application-factory and blueprint structure.

## Current stack

- Python 3.13, Flask 3, Gunicorn, Docker Compose.
- MySQL through `PyMySQL`; do not add an ORM or migration framework without a demonstrated need.
- Logging through the installed `sclog_lite` package from the `sun_course` project; do not use stdlib `logging` in application code.
- Student generation through `random_student_info`; do not hand-roll Chinese person data.
- DataTables 3.0.2 with Bootstrap 5 styling, loaded only by the manual-student page and without jQuery.

## Manual-student contract

- POST `/students/add-manual` validates input, performs a parameterized `INSERT`, commits, and redirects back to the list page.
- `students` uses an auto-increment `id`, `name`, `gender`, `birthday`, and `created_at`.
- The list query returns at most the latest 1000 rows using `ORDER BY created_at DESC, id DESC LIMIT 1000`; keep the ID tie-breaker.
- Age is a query-time continuous-age column: `ROUND(DATEDIFF(CURDATE(), birthday) / 365.2425, 1)`. Do not store age in MySQL.
- DataTables defaults to saved-time descending and ID descending. Keep its column indexes aligned when table columns change.
- A missing database must produce a user-safe message and server log; never expose credentials or raw connection details in the page.

## Database and configuration

- Read `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD` from the environment.
- Never commit passwords, root credentials, `.env` contents, or machine-specific secrets.
- Use the application account, never MySQL root. Parameterize all user-controlled SQL values.
- Treat existing database data as persistent user data. Do not run `DROP`, `TRUNCATE`, unrestricted `DELETE`/`UPDATE`, or destructive schema changes without explicit authorization.
- `CREATE TABLE IF NOT EXISTS students` is the current bootstrap strategy; introduce migrations only when schema evolution actually requires them.

## Verification

Run the smallest relevant checks after a change:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m mypy .
```

For deployment-file changes, also run `docker compose config --quiet` with `MYSQL_PASSWORD` set and `bash -n update.sh`. Tests must not write to the remote database; mock PyMySQL unless a live write was explicitly authorized.

## Deployment

- `update.sh` is the production update entrypoint. Keep its tracked-worktree guard, `git pull --ff-only`, Compose validation, image rebuild, and detached restart.
- Do not add `git reset`, `git clean`, forced checkout, forced pull, or automatic database mutation to the update script.
- The Compose deployment expects the external `app-network` and an externally supplied `MYSQL_PASSWORD`.
