from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.config import load_config
from app.fetcher import fetch_site

DEFAULT_CONFIG_PATH = "config/sites.yaml"


def _timestamp_for_filename(dt) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def cmd_fetch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        site = config.get_site(args.site)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"Fetching '{site.id}' ({site.url}) ...")
    result = fetch_site(site, config.settings.playwright)

    storage_root = Path(config.settings.storage.root)
    raw_dir = storage_root / site.id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"{_timestamp_for_filename(result.fetched_at)}.html"
    out_path.write_text(result.html)

    print(f"Title:      {result.title}")
    print(f"HTML bytes: {len(result.html)}")
    print(f"Saved to:   {out_path}")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
