# feedtidy

Real feeds are messier than the spec suggests. Dates show up in RFC 2822,
RFC 3339, or something a CMS made up. HTML entities get escaped twice.
Descriptions come padded with newlines and tabs from whatever template
generated them. feedtidy reads an RSS 2.0 or Atom document and produces
items with a single consistent shape: clean title, clean link, clean
description, and a date normalized to ISO 8601 UTC (or `null` if it truly
can't be parsed).

## Usage

From a file:

```
$ feedtidy example.xml
1. Local council approves new bike lanes
   https://example.com/news/bike-lanes
   published: 2026-03-04T14:30:00Z
   Council members voted 5-2 to approve the plan after months of debate.
```

From stdin (the default when no path is given):

```
$ curl -s https://example.com/feed.xml | feedtidy
```

Or point it straight at a feed URL:

```
$ feedtidy https://example.com/feed.xml
```

JSON output for piping into something else:

```
$ feedtidy example.xml --json
[
  {
    "title": "Local council approves new bike lanes",
    "link": "https://example.com/news/bike-lanes",
    "description": "Council members voted 5-2 to approve the plan after months of debate.",
    "published": "2026-03-04T14:30:00Z",
    "guid": "https://example.com/news/bike-lanes",
    "image": null
  }
]
```

## Library use

```python
from feedtidy import parse_items

with open("example.xml", encoding="utf-8") as f:
    items = parse_items(f.read())

for item in items:
    print(item.title, item.published)
```

## Status

Handles RSS 2.0 and Atom, including content:encoded (preferred over
`<description>` when both are present) and an item image pulled from
media:thumbnail, media:content, or `<enclosure>`.

## Install

No dependencies beyond the Python standard library (3.10+). Clone the repo
and run it with `python -m feedtidy.cli`, or install it locally:

```
$ pip install -e .
$ feedtidy --help
```

## Testing

```
$ python -m unittest discover -s tests
```

## License

MIT, see LICENSE.
