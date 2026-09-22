"""Command line entry point for feedtidy."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Optional, Sequence

from .parser import FeedItem, FeedParseError, parse_items

_REQUEST_TIMEOUT = 15
# A default urllib User-Agent gets a 403 from some feed hosts that block
# generic scrapers, so send something that looks like a normal client.
_USER_AGENT = "feedtidy/0.1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feedtidy",
        description="Normalize a messy RSS feed into clean, readable items.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help=(
            "path to an RSS XML file, a http:// or https:// URL, or '-' to "
            "read from stdin (default: stdin)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print items as a JSON array instead of human-readable text",
    )
    return parser


def _is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def _read_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    if _is_url(path):
        return _read_url(path)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def render_human(items: list[FeedItem]) -> str:
    if not items:
        return "(no items found)"
    lines = []
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. {item.title or '(untitled)'}")
        if item.link:
            lines.append(f"   {item.link}")
        if item.published:
            lines.append(f"   published: {item.published}")
        if item.image:
            lines.append(f"   image: {item.image}")
        if item.description:
            snippet = item.description
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            lines.append(f"   {snippet}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        xml_text = _read_input(args.path)
    except OSError as exc:
        print(f"feedtidy: couldn't read {args.path}: {exc}", file=sys.stderr)
        return 1

    try:
        items = parse_items(xml_text)
    except FeedParseError as exc:
        print(f"feedtidy: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps([item.to_dict() for item in items], indent=2))
    else:
        print(render_human(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
