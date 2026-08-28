# Henry - Career Page Scraper

- Lets a user maintain a list of tracked career pages (companies), each with its own scrape frequency.
- Uses an LLM to translate the scraped content into structured job listings (title, location, department, salary, etc.).
- Emails the user if a scrape finds new postings matching their preferences.

## Repo layout

- **`backend/`** — Django + Ninja REST API, Postgres via Django's ORM, the Playwright fetcher, and the LLM extractor.
- **`frontend/`** — React + TypeScript (Vite) single-page app.
- **`docs/`** — architecture, schema, and roadmap docs (see links at the bottom of this file).

## Getting started

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- A local Postgres instance running
- An API key for whichever LLM provider `LLM_PROVIDER` is set to in `.env`

### Backend

#### 1. Configure environment

```sh
cd backend
cp .env.example .env
```

Fill in `.env`:
- `LLM_PROVIDER` — `gemini` or `claude`
- `LLM_MODEL` — model name/id for that provider (e.g. `claude-haiku-4-5`)
- `LLM_API_KEY` — API key for that provider
- `DATABASE_URL` — connection string for your local Postgres instance

#### 2. Create the database

```sh
createdb career_scraper   # or whatever database name your DATABASE_URL points to
```

#### 3. Start the server

```sh
./backend-start.sh
```

This installs Python dependencies (`uv sync`), installs the Playwright browser, runs database migrations, then starts the dev server — safe to re-run any time (each step is a no-op if already up to date).

The API is now live at `http://127.0.0.1:8000/api/`.Django Ninja's interactive API console (Swagger UI) is at `http://127.0.0.1:8000/api/docs`.

#### 4. Create an admin user
```sh
uv run python manage.py createsuperuser
```


#### 5. Seed some companies

[`tests/test_seed_companies.py`](./backend/tests/test_seed_companies.py) creates 3 real companies (Uplight, Voltus, Development Seed), owned by a user account, by logging in and then hitting `POST /api/companies` on the server you just started — a quick way to bootstrap data on a fresh database. It's safe to re-run (companies that already exist, for that user, are skipped).

Pass the credentials for your admin user created above to run the command.

```sh
CAREER_SCRAPER_SEED_USERNAME=<username> CAREER_SCRAPER_SEED_PASSWORD=<password> uv run python tests/test_seed_companies.py
```

### Frontend

```sh
cd frontend
./frontend-start.sh
```

This installs npm dependencies and starts the dev server. Opens at `http://localhost:5173/`. The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8000`, so no CORS setup is needed — just make sure the backend is running on port 8000 first.

## Fast Launch

Once the above setup is complete, the entire suite can be managed along with a Grafana container and TMUX sessions with two simple commands.

```sh
./start-all.sh
./stop-all.sh
```

For the always-on home-server deployment (Gunicorn + Caddy + scheduler, no tmux),
use `./server-start.sh` instead — see [`production-deployment.md`](./docs/production-deployment.md).

## Docs in this folder

- [`architecture.md`](./docs/architecture.md) — system components, data flow, and repo structure.
- [`config-schema.md`](./docs/config-schema.md) — settings file format and the `Company` model.
- [`job-schema.md`](./docs/job-schema.md) — the `JobPosting` schema for an extracted job posting.
- [`roadmap.md`](./docs/roadmap.md) — phased build plan (V1/V2/V3) and open questions/risks.
- [`production-deployment.md`](./docs/production-deployment.md) — running Henry as an always-on service on a home server (in progress).
