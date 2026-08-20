from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from app.config import load_config
from app.extractor import get_extractor, to_job_postings
from app.fetcher import fetch_site
from app.storage import write_raw_html, write_snapshot

DEFAULT_CONFIG_PATH = "config/sites.yaml"


def cmd_fetch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        site = config.get_site(args.site)
    except KeyError as e:
        print(str(e), file=sys.stderr)
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
        site = config.get_site(args.site)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"Fetching '{site.id}' ({site.url}) ...")
    result = fetch_site(site, config.settings.playwright)
    print(f"Fetched {len(result.text)} chars of visible text.")

    extractor = get_extractor(config.settings.llm)
    print(f"Extracting jobs via {config.settings.llm.provider} ({config.settings.llm.model}) ...")
    extracted = extractor.extract(result.text)
    jobs = to_job_postings(
        extracted, site_id=site.id, source_url=site.url, scraped_at=result.fetched_at
    )

    out_path = write_snapshot(config.settings.storage.root, site.id, result.fetched_at, jobs)

    print(f"Found {len(jobs)} job(s):")
    for job in jobs:
        print(f"  - {job.title}" + (f" ({job.location})" if job.location else ""))
    print(f"Saved to: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="career-scraper")
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG_PATH, help="Path to sites config YAML"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch a single configured site's page and save the raw HTML"
    )
    fetch_parser.add_argument("--site", required=True, help="Site id from the config")
    fetch_parser.set_defaults(func=cmd_fetch)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Fetch a site and extract structured job postings into a timestamped JSON snapshot",
    )
    extract_parser.add_argument("--site", required=True, help="Site id from the config")
    extract_parser.set_defaults(func=cmd_extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
