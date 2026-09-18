"""Unit tests for the date and entity normalization helpers.

These two functions are where real-world feeds actually break: dates come
in RFC 2822, RFC 3339, or something a CMS invented, and entities get
escaped more than once by tools that don't know better.
"""

from __future__ import annotations

import unittest

from feedtidy.parser import clean_text, normalize_date


class CleanTextTests(unittest.TestCase):
    def test_none_returns_empty_string(self):
        self.assertEqual(clean_text(None), "")

    def test_empty_string_returns_empty_string(self):
        self.assertEqual(clean_text(""), "")

    def test_collapses_internal_whitespace(self):
        self.assertEqual(clean_text("hello\n\t  world  \n"), "hello world")

    def test_strips_leading_and_trailing_whitespace(self):
        self.assertEqual(clean_text("   padded   "), "padded")

    def test_unescapes_named_entities(self):
        self.assertEqual(clean_text("Tom &amp; Jerry"), "Tom & Jerry")
        self.assertEqual(clean_text("&quot;quoted&quot;"), '"quoted"')

    def test_unescapes_numeric_entities(self):
        self.assertEqual(clean_text("caf&#233;"), "café")
        self.assertEqual(clean_text("it&#39;s"), "it's")

    def test_unescapes_double_encoded_entities(self):
        # Some CMSes run their own escaping pass on top of the feed
        # generator's, producing "&amp;amp;" for a literal ampersand.
        self.assertEqual(clean_text("Tom &amp;amp; Jerry"), "Tom & Jerry")

    def test_unescapes_triple_encoded_entities(self):
        self.assertEqual(clean_text("&amp;amp;lt;div&amp;amp;gt;"), "<div>")

    def test_leaves_bare_ampersand_alone(self):
        self.assertEqual(clean_text("R&D"), "R&D")


class NormalizeDateTests(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(normalize_date(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(normalize_date(""))

    def test_unparseable_string_returns_none(self):
        self.assertIsNone(normalize_date("not a date"))

    def test_rfc2822_with_named_zone(self):
        self.assertEqual(
            normalize_date("Wed, 04 Mar 2026 14:30:00 GMT"),
            "2026-03-04T14:30:00Z",
        )

    def test_rfc2822_with_numeric_offset_converts_to_utc(self):
        self.assertEqual(
            normalize_date("Wed, 04 Mar 2026 14:30:00 -0500"),
            "2026-03-04T19:30:00Z",
        )

    def test_rfc2822_is_stripped_of_surrounding_whitespace(self):
        self.assertEqual(
            normalize_date("  Wed, 04 Mar 2026 14:30:00 GMT  "),
            "2026-03-04T14:30:00Z",
        )

    def test_rfc3339_with_z_suffix(self):
        self.assertEqual(
            normalize_date("2026-03-04T14:30:00Z"),
            "2026-03-04T14:30:00Z",
        )

    def test_rfc3339_with_colon_offset_converts_to_utc(self):
        self.assertEqual(
            normalize_date("2026-03-04T14:30:00+02:00"),
            "2026-03-04T12:30:00Z",
        )

    def test_rfc3339_with_fractional_seconds_and_z(self):
        self.assertEqual(
            normalize_date("2026-03-04T14:30:00.123456Z"),
            "2026-03-04T14:30:00Z",
        )

    def test_rfc3339_with_fractional_seconds_and_offset(self):
        self.assertEqual(
            normalize_date("2026-03-04T14:30:00.5+00:00"),
            "2026-03-04T14:30:00Z",
        )

    def test_space_separated_datetime_assumed_utc(self):
        self.assertEqual(
            normalize_date("2026-03-04 14:30:00"),
            "2026-03-04T14:30:00Z",
        )

    def test_date_only_assumed_midnight_utc(self):
        self.assertEqual(normalize_date("2026-03-04"), "2026-03-04T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
