# Production Deployment Plan (home server / mini PC)

Status: **in progress** — items 1–5 done, `/api/health` + weekly snapshot
retention done; remaining: off-box backup copy (5), mini-PC resource tuning (6),
`JobPosting` retention (7). Target: run Henry as a persistent always-on service
on a mini PC, reachable at `henry.fourthwallride.com` via a Cloudflare tunnel.

This is the gap between the current dev setup (`runserver` + Vite dev server in
tmux, `DEBUG=True`, in-process scheduler thread, no backups) and a deployment
that survives crashes, reboots, and doesn't silently multiply work.

Work items are ordered by priority. Each is independently landable.

---

## 1. Make Django settings production-safe  ✅ done

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
      `staticfiles/` gitignored. `collectstatic` runs in `server-deploy.sh` (item 4).

`manage.py check --deploy` is clean in prod mode. Hermetic coverage in
`backend/tests/test_settings.py`.

## 2. Serve properly (Gunicorn + built frontend + Caddy behind Cloudflare Tunnel)  ✅ done

`runserver` / Vite dev server are no longer used in production. Ingress:

```
browser → Cloudflare edge (TLS) → cloudflared tunnel → Caddy :8080 (HTTP) → Gunicorn :8000
                                                        ↘ frontend/dist (static SPA)
```

New at repo root:

- **`deploy/run-{web,scheduler,caddy}.sh`** — the per-service launchers
  (Gunicorn / `manage.py run_scheduler` / Caddy). Used as the systemd `ExecStart`
  (item 4). Each sources `backend/.env`; none of them run cloudflared (its own
  service).
- **`Caddyfile`** — local HTTP router only (`auto_https off`, listens on
  `HENRY_HTTP_PORT`, default 8080). Serves the built SPA, proxies `/api/*`
  `/controls/*` `/static/*` to Gunicorn, and forces `X-Forwarded-Proto: https`
  upstream since the real TLS hop is at Cloudflare. Env: `HENRY_HTTP_PORT`,
  `HENRY_FRONTEND_DIST`, `HENRY_BACKEND_BIND`. No ACME, no `setcap`, no open
  inbound ports. (To expose the box directly instead: switch the site address to
  `{$HENRY_DOMAIN}` and drop the header override — Caddy then does Let's Encrypt.)
- `gunicorn` added to `pyproject.toml`. Run with 3 workers, `--max-requests`
  recycling, and `--timeout 60` (`GUNICORN_TIMEOUT`). The scrape endpoints run
  synchronously in the worker, so that 60s also bounds a UI-triggered scrape
  before the worker is killed — a large `scrape-all` can still exceed it; the
  real fix (background jobs for scrape-all) is deferred.
- Frontend already calls `/api/*` relative — nothing to configure, Caddy routes it.
- cloudflared ingress rule: `henry.fourthwallride.com → http://localhost:8080`.

Still open: OpenTelemetry instrumentation of Gunicorn (item 6 — currently runs
plain, no `opentelemetry-instrument` wrapper).

## 3. Move the scheduler out of the web process  ✅ done

`apps.py:_should_start_scheduler()` used to return `True` unconditionally under
any WSGI server — every Gunicorn worker would start its own scheduler thread
(Nx the scrapes / LLM spend / load on target sites per tick).

- [x] `manage.py run_scheduler` — new management command
      (`app/management/commands/run_scheduler.py`), runs `scheduler._run_loop()`
      in the foreground as its own process.
- [x] `_should_start_scheduler()` WSGI branch now returns
      `os.environ.get("HENRY_RUN_SCHEDULER") == "1"` (default off). `runserver` +
      `RUN_MAIN` dev behaviour unchanged. Only `deploy/run-scheduler.sh` sets the
      env var; Gunicorn never sees it.
- [x] Coverage: `ShouldStartSchedulerTest` in `tests/test_scheduler.py`.
- [x] Runs as its own single-instance systemd service `henry-scheduler` (item 4).

Benefit beyond the bug fix: restart the web app without interrupting an
in-progress scrape, and vice versa.

## 4. Process supervision with systemd (replaces tmux)  ✅ done (branch `prod-systemd`)

Two scripts at repo root drive the whole lifecycle; Postgres and cloudflared
stay as their own services.

- **`server-deploy.sh`** — `uv sync` → `playwright install chromium` → build
  frontend → **`deploy/backup-db.sh`** (item 5) → `migrate` → `collectstatic` →
  (re)write the three unit files → `daemon-reload` → `enable` + `restart`.
  Deploys the working tree as-is (`git pull` yourself first). Takes no arguments.
  Run as the app user; it `sudo`s only for the systemd parts. Warns if the
  system timezone is UTC (scheduler matches cron against server-local time).
- **`server-teardown.sh`** — `deploy/backup-db.sh` (final snapshot) → `disable
  --now` + delete the three unit files + `daemon-reload` + `reset-failed`.
  Prompts unless `--yes`. Leaves cloudflared, Postgres, the repo, and the DB
  contents untouched.

Units (generated by `server-deploy.sh`, `User=`/`Group=` = the deploying user,
absolute paths + `PATH` baked in, `Restart=always`, `WantedBy=multi-user.target`):

| unit | ExecStart | WorkingDirectory |
|---|---|---|
| `henry-web.service` | `deploy/run-web.sh` (Gunicorn) | `backend/` — `load_config()` reads `config/settings.yaml` relative to CWD |
| `henry-scheduler.service` | `deploy/run-scheduler.sh` (`manage.py run_scheduler`, `HENRY_RUN_SCHEDULER=1`) | `backend/` |
| `henry-caddy.service` | `deploy/run-caddy.sh` | repo root |

The `deploy/run-*.sh` launchers are the single source of truth for how each
service starts. Config comes from `backend/.env` (sourced by each launcher), not
an `EnvironmentFile`. To run one in the foreground for debugging:
`sudo systemctl stop henry-web && ./deploy/run-web.sh`.

Logs → journald (`LOGGING` writes to stdout): `journalctl -u henry-web -f`.

`server-start.sh` also installs a weekly-maintenance entry in the deploying user's
crontab (`deploy/maintenance-cron.sh install`); `server-stop.sh` removes it. See
items 5 and 7.

## 5. Backups

Context: a schema migration wiped the dev DB once already.

- [x] **`deploy/backup-db.sh`** — `pg_dump -Fc` to `$HENRY_BACKUP_DIR`
      (default `~/backups/henry`), filename `henry-<timestamp>[-<label>].dump`,
      then prunes to the **10 most recent**. `server-deploy.sh` runs it (labelled
      `deploy`) right before `migrate` and aborts if it fails; `server-teardown.sh`
      runs it (labelled `teardown`) but continues on failure.
- [x] **Decouple `migrate` from service start** — item 4. `migrate` / build /
      backup all live in `server-deploy.sh`; the units just run the app.
- [x] **Scheduled** dumps — `deploy/weekly-maintenance.sh` runs
      `deploy/backup-db.sh weekly` (+ snapshot pruning, item 7) from the deploying
      user's crontab. `server-start.sh` installs the entry via
      `deploy/maintenance-cron.sh install` (schedule `HENRY_MAINTENANCE_CRON`,
      default `0 4 * * 0`); `server-stop.sh` removes it by marker block. Chosen
      over a `henry-backup.timer` to keep one mechanism and reuse the existing
      10-most-recent prune. Missed if the box is off across the scheduled hour —
      no catch-up.
- [ ] **Off-box copy**: rsync a recent dump to another machine or object store.
      A dead SSD takes local-only backups with it.
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

- [x] Unauthenticated `GET /api/health` → `{"status": "ok"}` for Caddy / systemd
      / uptime checks (`api.py`, `auth=None`, no DB access). Test in
      `tests/test_api_health.py`.
- [x] Age-based raw-HTML snapshot retention. `clear-snapshots.sh` takes an
      optional `N` = delete only files older than N days (no arg = wipe all).
      `deploy/weekly-maintenance.sh` calls it with `HENRY_SNAPSHOT_RETENTION_DAYS`
      (default 7); runs weekly from the same cron entry as the DB dump (item 5).
- [ ] Consider a `JobPosting` retention policy once history accumulates — see
      roadmap "Open questions / risks".

---

## Not doing (and why)

- **Docker Compose instead of systemd** — viable alternative; systemd chosen
  because Postgres is already a host service and Playwright-in-container adds
  browser-dependency friction. Revisit if the mini PC gets rebuilt.
- **Multiple app servers / load balancing** — single-user personal project, not
  in scope (see roadmap scope note).
