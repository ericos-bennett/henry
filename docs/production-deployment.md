# Production Deployment Plan (home server / mini PC)

Status: **not yet implemented** — plan only. Target: run Henry as a persistent
always-on service on a LAN mini PC, reachable at `henry.fourthwallride.com`.

This is the gap between the current dev setup (`runserver` + Vite dev server in
tmux, `DEBUG=True`, in-process scheduler thread, no backups) and a deployment
that survives crashes, reboots, and doesn't silently multiply work.

Work items are ordered by priority. Each is independently landable.

---

## 1. Make Django settings production-safe  ✅ done (branch `prod-settings`)

`backend/src/app/settings.py` used to hardcode `DEBUG = True` and a dev
`SECRET_KEY`. Now environment-driven:

- [x] `DEBUG = os.environ.get("DJANGO_DEBUG", "").lower() == "true"` (default False).
      Local `.env` and `.env.example` set `DJANGO_DEBUG=true`.
- [x] `SECRET_KEY` — dev fallback only when `DEBUG`; with `DEBUG` off, a missing
      `DJANGO_SECRET_KEY` raises `ImproperlyConfigured` at startup.
      Generate: `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- [x] `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` — already env-driven; `.env` carries
      `henry.fourthwallride.com`. `.env.example` comment updated.
- [x] `CONN_MAX_AGE = 60` in `_database_from_url()`
- [x] TLS-behind-proxy hardening — gated behind `DJANGO_SECURE_SSL=true` (keep off
      until Caddy terminates TLS — item 2): `SECURE_PROXY_SSL_HEADER`,
      `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`
      (+ `INCLUDE_SUBDOMAINS`, `PRELOAD`), `SECURE_SSL_REDIRECT`.
- [x] Added `SecurityMiddleware`, `WhiteNoiseMiddleware`, `XFrameOptionsMiddleware`
      to `MIDDLEWARE`; `whitenoise` in `pyproject.toml`; `STATIC_ROOT`,
      `STORAGES["staticfiles"]` → `whitenoise.storage.CompressedStaticFilesStorage`;
      `staticfiles/` gitignored. `collectstatic` still needs adding to `deploy.sh`
      (item 5).

`manage.py check --deploy` is clean in prod mode. Hermetic coverage in
`backend/tests/test_settings.py`.

## 2. Serve properly (Gunicorn + built frontend + Caddy)

Stop using `runserver` and the Vite dev server.

- [ ] **Backend**: add `gunicorn` to `pyproject.toml`. Run
      `gunicorn app.wsgi:application --workers 3 --bind 127.0.0.1:8000`
      (`app/wsgi.py` already exists). 2–3 workers is plenty for personal use.
- [ ] **Frontend**: `npm run build` produces `frontend/dist/`. Serve it as
      static files — do not run Vite in production. The `/api` proxy currently
      done by Vite moves to Caddy.
- [ ] **Reverse proxy**: Caddy. Serves `frontend/dist`, proxies `/api/*` and
      `/controls/*` to `127.0.0.1:8000`, terminates TLS automatically via
      Let's Encrypt. Sketch Caddyfile:

      ```
      henry.fourthwallride.com {
          root * /srv/henry/frontend/dist
          @backend path /api/* /controls/* /static/*
          handle @backend {
              reverse_proxy 127.0.0.1:8000
          }
          handle {
              try_files {path} /index.html
              file_server
          }
      }
      ```

## 3. Move the scheduler out of the web process  ⚠️ correctness bug otherwise

`backend/src/app/apps.py:_should_start_scheduler()` returns `True`
**unconditionally** when the app is not launched via `manage.py` — i.e. under
*any* WSGI server. Every Gunicorn worker would start its own scheduler thread:
3 workers ⇒ every company scraped 3× per tick, 3× the LLM spend, 3× the load on
target sites.

- [ ] Add a management command `manage.py run_scheduler` that calls
      `app.scheduler._run_loop()` (already module-level in `scheduler.py`).
- [ ] Change `_should_start_scheduler()` so it never auto-starts under WSGI —
      gate the non-`manage.py` branch on an env var (e.g.
      `HENRY_RUN_SCHEDULER=1`) that only the management command / its systemd
      unit sets. Keep the existing `runserver` + `RUN_MAIN` behaviour for local
      dev.
- [ ] Run the command as its own single-instance systemd service (item 4).

Benefit beyond the bug fix: restart the web app without interrupting an
in-progress scrape, and vice versa.

## 4. Process supervision with systemd (replaces tmux)

tmux doesn't restart on crash or start on boot. Create three units (Postgres and
Caddy run as their own distro services):

- [ ] `henry-web.service` — Gunicorn. `Restart=always`,
      `WorkingDirectory=/srv/henry/backend` (**required** — `load_config()`
      reads `config/settings.yaml` relative to CWD),
      `EnvironmentFile=/srv/henry/backend/.env`
- [ ] `henry-scheduler.service` — `manage.py run_scheduler`. `Restart=always`,
      `Environment=HENRY_RUN_SCHEDULER=1`, same `WorkingDirectory`.
- [ ] `henry-backup.timer` + `henry-backup.service` — item 5.
- [ ] `systemctl enable --now` all of them. `WantedBy=multi-user.target` for
      boot start.
- [ ] Set the mini PC's system timezone correctly — the scheduler matches cron
      expressions against **server-local** time (`scheduler.py`, `local_now`).

Logs go to journald automatically (`LOGGING` already writes to stdout);
`journalctl -u henry-web -f`.

## 5. Backups  🔴 do this first — production data has no safety net today

Context: a schema migration wiped the dev DB once already. There is no dump, and
Postgres.app ships with `archive_mode = off`.

- [ ] `henry-backup.service`: `pg_dump -Fc career_scraper > /backups/henry-$(date +%F-%H%M).dump`
- [ ] `henry-backup.timer`: daily (or hourly if scrape volume grows).
- [ ] Retention: keep ~7 daily + ~4 weekly, prune older. Simple `find -mtime`
      prune step in the service script.
- [ ] **Off-box copy**: rsync at least one recent dump to another machine or a
      cheap object store. A dead SSD takes local-only backups with it.
- [ ] **Decouple `migrate` from service start.** `backend-start.sh` runs
      `uv sync` + `migrate` on every launch — a crash-looping unit would re-run
      migrations. Move deploy steps into a separate `deploy.sh`:
      `git pull` → `uv sync` → `playwright install --with-deps chromium` →
      `pg_dump` (pre-migration snapshot) → `manage.py migrate` →
      `manage.py collectstatic --noinput` → `npm ci && npm run build` →
      `systemctl restart henry-web henry-scheduler`.
- [ ] Any future migration that drops/flushes rows: take an explicit named dump
      and confirm before running. (See memory: data-loss changes need an upfront
      backup plan.)

## 6. Resource tuning for a mini PC

- [ ] `backend/config/settings.yaml`: drop `playwright.max_concurrency` from `4`
      to `1` or `2`. Each headless Chromium is ~200–300 MB and the per-company
      LLM call runs in the same worker thread — 4 at once can OOM a small box.
- [ ] `playwright install --with-deps chromium` for system libs; re-run after
      every Playwright upgrade (it's in `deploy.sh` above).
- [ ] **OpenTelemetry / otel-lgtm is a ~1 GB-RAM Grafana+Prometheus+Loki
      stack.** Decide:
      - drop it — set `OTEL_TRACES_EXPORTER` / `OTEL_METRICS_EXPORTER` /
        `OTEL_LOGS_EXPORTER` to `none`, rely on journald; or
      - run the collector on a different machine and point
        `OTEL_EXPORTER_OTLP_ENDPOINT` at it.
      Either way it should not be a hard dependency of `start-all.sh` in prod.
- [ ] Gunicorn workers: 2–3, not more.

## 7. Minor / nice-to-have

- [ ] Add an unauthenticated `GET /api/health` returning `{"status": "ok"}` for
      Caddy / systemd / uptime checks. (Every current endpoint needs auth.)
- [ ] Schedule `clear-snapshots.sh` (raw HTML dumps under `backend/data/*/raw/`
      grow unbounded) on a weekly systemd timer, or add age-based retention.
- [ ] Consider a `JobPosting` retention policy once history accumulates — see
      roadmap "Open questions / risks".

---

## Not doing (and why)

- **Docker Compose instead of systemd** — viable alternative; systemd chosen
  because Postgres is already a host service and Playwright-in-container adds
  browser-dependency friction. Revisit if the mini PC gets rebuilt.
- **Multiple app servers / load balancing** — single-user personal project, not
  in scope (see roadmap scope note).
