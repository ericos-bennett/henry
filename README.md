# Henry - Career Page Scraper

- Lets a user maintain a list of tracked career pages (companies), each with its own scrape frequency.
- Uses an LLM to translate the scraped content into structured job listings (title, location, department, salary, etc.).
- Emails the user if a scrape finds new postings matching their preferences.

## Repo Layout

- **`backend/`** — Django + Ninja REST API, Postgres via Django's ORM, the Playwright fetcher, and the LLM extractor.
- **`frontend/`** — React + TypeScript (Vite) single-page app.
- **`infra/`** — Helper scripts for running the system on a linux server (see bottom of this doc)

## Getting Started

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- A local Postgres instance running
- An API key for whichever LLM provider `LLM_PROVIDER` is set to in `.env`

### Backend

#### 1. Configure Environment

```sh
cd backend
cp .env.example .env
# Fill in .env
```

#### 2. Create Database

```sh
createdb career_scraper   # or whatever database name your DATABASE_URL points to
```

#### 3. Start Server

```sh
./backend-start.sh
```

This installs Python dependencies (`uv sync`), installs the Playwright browser, runs database migrations, then starts the dev server — safe to re-run any time (each step is a no-op if already up to date).

The API is now live at `http://127.0.0.1:8000/api/`.Django Ninja's interactive API console (Swagger UI) is at `http://127.0.0.1:8000/api/docs`.

#### 4. Create Admin User
```sh
uv run python manage.py createsuperuser
```

#### 5. Run Tests

From `backend/`, with Postgres running (Django creates and drops its own test database):

```sh
uv run python manage.py test
```

### Frontend

```sh
cd frontend
./frontend-start.sh
```

This installs npm dependencies and starts the dev server. Opens at `http://localhost:5173/`. The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8000`, so no CORS setup is needed — just make sure the backend is running on port 8000 first.

## Fast Launch (Local Development)

Once the above setup is complete, the entire suite can be managed along with a Grafana container and TMUX sessions with two simple commands.

```sh
./local-start.sh
./local-stop.sh
```

## Fast Launch (Home Server)

```sh
./server-start.sh
./server-stop.sh
```