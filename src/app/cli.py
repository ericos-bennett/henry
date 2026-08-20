from __future__ import annotations

from app.django_setup import ensure_django_setup

ensure_django_setup()

import argparse
import sys

from app.config import load_config
from app.extractor import get_extractor, to_job_postings
from app.fetcher import fetch_site
from app.models import Site
from app.storage import save_job_postings, write_raw_html

DEFAULT_CONFIG_PATH = "config/settings.yaml"


def cmd_fetch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        site = Site.objects.get(pk=args.site)
    except Site.DoesNotExist:
        print(f"No site with id '{args.site}'", file=sys.stderr)
        return 1

    print(f"Fetching '{site.id}' ({site.url}) ...")
    result = fetch_site(site, config.settings.playwright)

    out_path = write_raw_html(
        config.settings.storage.root, site.id, result.fetched_at, result.html
    )

    print(f"Title:      {result.title}")
    print(f"HTML bytes: {len(result.html)}")
    print(f"Saved to:   {out_path}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        site = Site.objects.get(pk=args.site)
    except Site.DoesNotExist:
        print(f"No site with id '{args.site}'", file=sys.stderr)
        return 1

    print(f"Fetching '{site.id}' ({site.url}) ...")
    result = fetch_site(site, config.settings.playwright)
    print(f"Fetched {len(result.text)} chars of visible text.")

    extractor = get_extractor(config.settings.llm)
    print(f"Extracting jobs via {config.settings.llm.provider} ({config.settings.llm.model}) ...")
    extracted = extractor.extract(result.text)
    jobs = to_job_postings(extracted, site=site, scraped_at=result.fetched_at)

    saved = save_job_postings(jobs)

    print(f"Found {len(saved)} job(s):")
    for job in saved:
        print(f"  - {job.title}" + (f" ({job.location})" if job.location else ""))
    print(f"Saved to Postgres (source_site='{site.id}', scraped_at={result.fetched_at.isoformat()}).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="career-scraper")
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG_PATH, help="Path to settings config YAML"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch a single configured site's page and save the raw HTML"
    )
    fetch_parser.add_argument("--site", required=True, help="Site id")
    fetch_parser.set_defaults(func=cmd_fetch)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Fetch a site and extract structured job postings into Postgres",
    )
    extract_parser.add_argument("--site", required=True, help="Site id")
    extract_parser.set_defaults(func=cmd_extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
