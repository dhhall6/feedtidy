"""Parse RSS 2.0 and Atom documents and normalize items into a consistent shape.

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

# Fallback date formats seen in feeds that don't follow RFC 2822. Atom
# favors RFC 3339, which allows fractional seconds RFC 2822 doesn't have.
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


class FeedParseError(ValueError):
    """Raised when the input doesn't look like an RSS or Atom feed we can read."""


@dataclass
class FeedItem:
    title: str
    link: str
    description: str
    published: Optional[str]  # ISO 8601 UTC, or None if unparseable
    guid: Optional[str]
    image: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "link": self.link,
            "description": self.description,
            "published": self.published,
            "guid": self.guid,
            "image": self.image,
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


def _local_name(tag: str) -> str:
    """Strip a namespace like '{http://www.w3.org/2005/Atom}entry' down to 'entry'.

    RSS elements are usually unnamespaced but Atom always lives in its own
    namespace, so matching on local name lets the same lookup helpers work
    for both formats.
    """
    return tag.rsplit("}", 1)[-1]


def _find_child(node: ET.Element, name: str) -> Optional[ET.Element]:
    for child in node:
        if _local_name(child.tag) == name:
            return child
    return None


def _find_children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if _local_name(child.tag) == name]


def _child_text(node: ET.Element, tag: str) -> Optional[str]:
    child = _find_child(node, tag)
    if child is None:
        return None
    return child.text


def _atom_link(entry: ET.Element) -> str:
    """Pick the entry's alternate (human-readable) link.

    Atom entries can carry several <link> elements distinguished by a
    'rel' attribute (alternate, self, enclosure, ...); a bare link with no
    rel defaults to alternate per the spec. Fall back to the first link if
    none is explicitly marked alternate.
    """
    links = _find_children(entry, "link")
    for link in links:
        if link.get("rel", "alternate") == "alternate":
            return clean_text(link.get("href"))
    if links:
        return clean_text(links[0].get("href"))
    return ""


def _atom_description(entry: ET.Element) -> str:
    content = _find_child(entry, "content")
    if content is not None and content.text:
        return clean_text(content.text)
    summary = _find_child(entry, "summary")
    if summary is not None and summary.text:
        return clean_text(summary.text)
    return ""


def _atom_date(entry: ET.Element) -> Optional[str]:
    published = _child_text(entry, "published")
    if published:
        return normalize_date(published)
    return normalize_date(_child_text(entry, "updated"))


def _rss_description(node: ET.Element) -> str:
    """Prefer content:encoded over <description> when both are present.

    content:encoded (the RSS content module) usually holds the full HTML
    body, while <description> is often just a short summary or the same
    text truncated. The plain <description> tag is the fallback for feeds
    that don't use the module at all.
    """
    encoded = _child_text(node, "encoded")
    if encoded:
        return clean_text(encoded)
    return clean_text(_child_text(node, "description"))


def _find_image(node: ET.Element) -> Optional[str]:
    """Pull an item image out of whatever namespaced field offers one.

    Checked in order of how likely each is to actually point at an image:
    media:thumbnail, then media:content (only if it's tagged as an image),
    then the plain RSS <enclosure> element. Shared between RSS items and
    Atom entries since media namespace elements show up in both.
    """
    thumbnail = _find_child(node, "thumbnail")
    if thumbnail is not None and thumbnail.get("url"):
        return clean_text(thumbnail.get("url"))

    for content in _find_children(node, "content"):
        medium = content.get("medium")
        content_type = content.get("type", "")
        if (medium == "image" or content_type.startswith("image/")) and content.get("url"):
            return clean_text(content.get("url"))

    enclosure = _find_child(node, "enclosure")
    if enclosure is not None and enclosure.get("type", "").startswith("image/") and enclosure.get("url"):
        return clean_text(enclosure.get("url"))

    return None


def _parse_rss(root: ET.Element) -> list[FeedItem]:
    channel = _find_child(root, "channel")
    if channel is None:
        raise FeedParseError("no <channel> element found - is this an RSS 2.0 feed?")

    items = []
    for node in _find_children(channel, "item"):
        items.append(
            FeedItem(
                title=clean_text(_child_text(node, "title")),
                link=clean_text(_child_text(node, "link")),
                description=_rss_description(node),
                published=normalize_date(_child_text(node, "pubDate")),
                guid=clean_text(_child_text(node, "guid")) or None,
                image=_find_image(node),
            )
        )
    return items


def _parse_atom(root: ET.Element) -> list[FeedItem]:
    items = []
    for entry in _find_children(root, "entry"):
        items.append(
            FeedItem(
                title=clean_text(_child_text(entry, "title")),
                link=_atom_link(entry),
                description=_atom_description(entry),
                published=_atom_date(entry),
                guid=clean_text(_child_text(entry, "id")) or None,
                image=_find_image(entry),
            )
        )
    return items


def parse_items(xml_text: str) -> list[FeedItem]:
    """Parse an RSS 2.0 or Atom document into a list of normalized FeedItem records."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FeedParseError(f"not well-formed XML: {exc}") from exc

    root_name = _local_name(root.tag)
    if root_name == "rss":
        return _parse_rss(root)
    if root_name == "feed":
        return _parse_atom(root)
    raise FeedParseError(
        f"unrecognized root element <{root_name}> - expected RSS 2.0 <rss> or Atom <feed>"
    )
