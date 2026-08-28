# Production Deployment Plan (home server / mini PC)

Status: **in progress** — items 1–3 done (branch `prod-serve`), items 4–7 remain.
Target: run Henry as a persistent always-on service on a mini PC, reachable at
`henry.fourthwallride.com` via a Cloudflare tunnel.

This is the gap between the current dev setup (`runserver` + Vite dev server in
tmux, `DEBUG=True`, in-process scheduler thread, no backups) and a deployment
that survives crashes, reboots, and doesn't silently multiply work.

Work items are ordered by priority. Each is independently landable.

---

## 1. Make Django settings production-safe  ✅ done (branch `prod-serve`)

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

## 2. Serve properly (Gunicorn + built frontend + Caddy behind Cloudflare Tunnel)  ✅ done (branch `prod-serve`)

`runserver` / Vite dev server are no longer used in production. Ingress:

```
browser → Cloudflare edge (TLS) → cloudflared tunnel → Caddy :8080 (HTTP) → Gunicorn :8000
                                                        ↘ frontend/dist (static SPA)
```

New at repo root:

- **`server-start.sh`** — production launcher. Builds the frontend, runs
  `collectstatic`, refuses to start with unapplied migrations or `DJANGO_DEBUG=true`,
  then runs Gunicorn + `run_scheduler` + Caddy together in the foreground with a
  cleanup trap (any one exiting stops the others). `--skip-build` to run only.
  Interim until systemd (item 4) — a systemd unit can just exec this script, or
  item 4 splits it into three units. Does **not** run cloudflared (its own service).
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

## 3. Move the scheduler out of the web process  ✅ done (branch `prod-serve`)

`apps.py:_should_start_scheduler()` used to return `True` unconditionally under
any WSGI server — every Gunicorn worker would start its own scheduler thread
(Nx the scrapes / LLM spend / load on target sites per tick).

- [x] `manage.py run_scheduler` — new management command
      (`app/management/commands/run_scheduler.py`), runs `scheduler._run_loop()`
      in the foreground as its own process.
- [x] `_should_start_scheduler()` WSGI branch now returns
      `os.environ.get("HENRY_RUN_SCHEDULER") == "1"` (default off). `runserver` +
      `RUN_MAIN` dev behaviour unchanged. `server-start.sh` sets the env var only
      on the `run_scheduler` subprocess, never on Gunicorn.
- [x] Coverage: `ShouldStartSchedulerTest` in `tests/test_scheduler.py`.
- [ ] Run as its own single-instance systemd service (item 4).

Benefit beyond the bug fix: restart the web app without interrupting an
in-progress scrape, and vice versa.

## 4. Process supervision with systemd (replaces tmux)

tmux doesn't restart on crash or start on boot. `server-start.sh` is the interim
supervisor; replace it with units (Postgres runs as its own distro service;
cloudflared as its own via `cloudflared service install`):

- [ ] `henry-web.service` — Gunicorn. `Restart=always`,
      `WorkingDirectory=/srv/henry/backend` (**required** — `load_config()`
      reads `config/settings.yaml` relative to CWD),
      `EnvironmentFile=/srv/henry/backend/.env`
- [ ] `henry-scheduler.service` — `manage.py run_scheduler`. `Restart=always`,
      `Environment=HENRY_RUN_SCHEDULER=1`, same `WorkingDirectory`.
- [ ] `henry-caddy.service` — `caddy run --config /srv/henry/Caddyfile
      --adapter caddyfile`, with the `HENRY_*` env vars set. `Restart=always`.
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
