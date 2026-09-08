"""Parse RSS 2.0 documents and normalize items into a consistent shape.

Feeds in the wild disagree on date formats, double-encode their HTML
entities, and pad descriptions with inconsistent whitespace. This module
picks one shape and coerces everything into it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Optional
from xml.etree import ElementTree as ET

_WHITESPACE_RE = re.compile(r"\s+")

# Fallback date formats seen in feeds that don't follow RFC 2822.
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


class FeedParseError(ValueError):
    """Raised when the input doesn't look like an RSS feed we can read."""


@dataclass
class FeedItem:
    title: str
    link: str
    description: str
    published: Optional[str]  # ISO 8601 UTC, or None if unparseable
    guid: Optional[str]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "link": self.link,
            "description": self.description,
            "published": self.published,
            "guid": self.guid,
        }


def clean_text(value: Optional[str]) -> str:
    """Collapse whitespace and unescape HTML entities.

    Some feed generators escape entities twice (e.g. "&amp;amp;"), so
    unescape repeatedly until it stops changing. Capped at a few passes
    so a pathological feed can't spin us forever.
    """
    if not value:
        return ""
    text = value
    for _ in range(3):
        unescaped = unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """Turn an RFC 2822 or common ISO-ish date string into ISO 8601 UTC."""
    if not raw:
        return None
    raw = raw.strip()

    dt = None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        dt = None

    if dt is None:
        for fmt in _DATE_FORMATS:
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text_of(node: ET.Element, tag: str) -> Optional[str]:
    child = node.find(tag)
    if child is None:
        return None
    return child.text


def parse_items(xml_text: str) -> list[FeedItem]:
    """Parse an RSS 2.0 document into a list of normalized FeedItem records."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FeedParseError(f"not well-formed XML: {exc}") from exc

    channel = root.find("channel")
    if channel is None:
        raise FeedParseError("no <channel> element found - is this an RSS 2.0 feed?")

    items = []
    for node in channel.findall("item"):
        items.append(
            FeedItem(
                title=clean_text(_text_of(node, "title")),
                link=clean_text(_text_of(node, "link")),
                description=clean_text(_text_of(node, "description")),
                published=normalize_date(_text_of(node, "pubDate")),
                guid=clean_text(_text_of(node, "guid")) or None,
            )
        )
    return items
