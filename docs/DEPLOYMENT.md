# Deployment Guide

This guide covers deploying JobMarket AI to a production environment. It
assumes a Linux host with Python 3.11+ available.

## 1. Environment variables

Copy `.env.example` to `.env` and set real values. At minimum, set the
following for production:

| Variable | Required | Notes |
|---|---|---|
| `FLASK_ENV` | yes | Set to `production` |
| `SECRET_KEY` | yes | Long random string. Never reuse the dev default. |
| `DATABASE_URL` | yes | Use an **absolute** path for SQLite (`sqlite:////var/lib/jobmarket-ai/app.db`) or a real server DSN (e.g. `postgresql://user:pass@host:5432/jobmarket`). A relative SQLite URL is resolved against Flask's `instance/` folder, not the project root — always use an absolute path or a real DB server in production. |
| `SESSION_COOKIE_SECURE` | yes | Set to `true` (requires HTTPS) |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | yes | Real SMTP credentials — without these, verification/reset emails only write to `logs/dev_emails.log` and users can never complete signup |
| `GEMINI_API_KEY_1..4`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | optional | Configure at least one for AI features (assistant, roadmap suggestions, resume improvement, ATS tips) to work. Without any key, those features degrade gracefully with an explicit "AI not configured" message rather than failing. |
| `AI_PROVIDER_ORDER` | optional | Comma-separated fallback order, e.g. `gemini,groq,openrouter,claude` |
| `REMEMBER_COOKIE_DAYS` | optional | Defaults to 14 |

Never commit `.env` or real API keys to version control.

## 2. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Database schema: use migrations, not `create_all()`

Local development and the test suite use a convenience `db.create_all()`
bootstrap on app startup for zero-friction setup against SQLite. **Production
must not rely on this.** Starting with this release, schema changes are
tracked with Flask-Migrate (Alembic) under `migrations/`.

First-time production setup:

```bash
export FLASK_APP=app.py
export FLASK_ENV=production
export DATABASE_URL="postgresql://user:pass@host:5432/jobmarket"   # or an absolute sqlite://// URL

flask db upgrade
```

This creates every table from the versioned migration history instead of an
implicit `create_all()`, so the schema is reproducible and auditable.

When you pull a new release that changes models, always run:

```bash
flask db upgrade
```

before restarting the app server. If you change a model yourself, generate
the migration with:

```bash
flask db migrate -m "describe the change"
flask db upgrade
```

then review the generated file under `migrations/versions/` before applying
it to a real database — autogenerate is a strong starting point, not a
guarantee, especially for column type changes or data backfills.

Note: when `sys.argv[1] == "db"` (i.e. you are running any `flask db ...`
command), the app skips its own `create_all()`/seed bootstrap so Alembic sees
a true, unmodified diff against your actual database state.

## 4. Seed reference data

Taxonomy and learning-resource seed data load automatically on normal app
startup (outside of `flask db ...` commands) when the environment is not
`testing`. To refresh the skill taxonomy manually at any time:

```bash
flask seed-taxonomy
```

## 5. Run with a production WSGI server

Do not use the Flask development server (`flask run`) in production. Use
gunicorn (or an equivalent WSGI server):

```bash
pip install gunicorn
gunicorn --workers 4 --bind 0.0.0.0:8000 --timeout 60 "app:create_app('production')"
```

Put a reverse proxy (nginx, Caddy) in front of gunicorn to terminate TLS,
serve `/static` efficiently, and set standard proxy headers
(`X-Forwarded-For`, `X-Forwarded-Proto`).

## 6. Health check

The app exposes:

```
GET /health
```

It returns `200 {"status": "ok", "checks": {"database": true}}` when the
database is reachable, or `503 {"status": "degraded", "checks": {"database": false}}`
otherwise. Point your load balancer's or uptime monitor's health check at
this endpoint rather than `/`, since `/` renders a full page and may require
authentication-aware logic in future changes.

## 7. File uploads and logs

`UPLOAD_FOLDER` and `LOG_DIR` (both under the project directory by default)
must be writable by the process user and should be backed by persistent
storage — not an ephemeral container filesystem — if you want resumes and
logs to survive a redeploy. Consider mounting a volume for both, or moving
them to object storage in a future iteration.

## 8. Production checklist

- [ ] `SECRET_KEY` is a long random value, not the dev default
- [ ] `DATABASE_URL` points at a real, backed-up database (an absolute-path SQLite file at minimum; Postgres recommended for concurrent production traffic)
- [ ] `flask db upgrade` has been run against that database
- [ ] `SESSION_COOKIE_SECURE=true` and the app is served over HTTPS
- [ ] Real SMTP credentials are set so verification/reset emails actually send
- [ ] At least one AI provider API key is set, if AI features are wanted
- [ ] App is run under gunicorn (or similar), not `flask run`
- [ ] A reverse proxy terminates TLS and forwards to gunicorn
- [ ] `/health` is wired into your load balancer or uptime monitor
- [ ] `UPLOAD_FOLDER` and `LOG_DIR` are on persistent, writable storage
- [ ] `DEBUG=false` (set automatically by `ProductionConfig`, but confirm `FLASK_ENV=production` is actually set)
- [ ] Database backups are scheduled
- [ ] Full test suite passes against the target Python version before deploying: `pytest -q`
