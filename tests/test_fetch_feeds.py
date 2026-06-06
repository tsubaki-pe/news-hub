from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import fetch_feeds


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item>
<title>Example &amp; News</title>
<link>https://example.com/story?utm_source=rss</link>
<pubDate>Thu, 04 Jun 2026 09:00:00 GMT</pubDate>
<description><![CDATA[<p>A useful summary.</p>]]></description>
</item></channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Atom story</title>
<link href="https://example.com/atom" rel="alternate"/>
<updated>2026-06-04T10:00:00Z</updated>
<summary>Atom summary</summary>
</entry></feed>"""


class FetchFeedsTests(unittest.TestCase):
    def test_parse_rss(self) -> None:
        with patch.object(fetch_feeds, "fetch_xml", return_value=RSS):
            items = fetch_feeds.parse_feed({"name": "Example", "url": "https://example.com/rss"})

        self.assertEqual(items[0]["title"], "Example & News")
        self.assertEqual(items[0]["excerpt"], "A useful summary.")
        self.assertEqual(items[0]["publishedAt"], "2026-06-04T09:00:00Z")

    def test_parse_atom_link_attribute(self) -> None:
        with patch.object(fetch_feeds, "fetch_xml", return_value=ATOM):
            items = fetch_feeds.parse_feed({"name": "Example", "url": "https://example.com/atom.xml"})

        self.assertEqual(items[0]["link"], "https://example.com/atom")

    def test_rejects_unsafe_link(self) -> None:
        self.assertEqual(fetch_feeds.safe_link("javascript:alert(1)"), "")

    def test_main_keeps_existing_output_when_all_feeds_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news.json"
            output.write_text("existing", encoding="utf-8")
            empty_news = {"generatedAt": "2026-06-04T00:00:00Z", "categories": [], "errors": []}
            with (
                patch.object(fetch_feeds, "build_news", return_value=empty_news),
                patch.object(sys, "argv", ["fetch_feeds.py", "--output", str(output)]),
            ):
                self.assertEqual(fetch_feeds.main(), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_enrich_without_api_key_keeps_original_fields(self) -> None:
        news = {
            "categories": [
                {
                    "name": "世界ニュース",
                    "items": [{"title": "Original", "excerpt": "Original excerpt", "link": "https://example.com"}],
                }
            ]
        }

        fetch_feeds.enrich_with_gemini(
            news, api_key=None, model="gemini-test", limit_per_category=10, batch_size=5, delay_seconds=0
        )

        item = news["categories"][0]["items"][0]
        self.assertEqual(item["title"], "Original")
        self.assertEqual(item["excerpt"], "Original excerpt")
        self.assertEqual(item["translationStatus"], "not_configured")
        self.assertFalse(news["translation"]["enabled"])

    def test_enrich_with_gemini_adds_japanese_summary(self) -> None:
        news = {
            "categories": [
                {
                    "name": "世界ニュース",
                    "items": [{"title": "Original", "excerpt": "Original excerpt", "link": "https://example.com"}],
                }
            ]
        }
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"items":[{"index":0,"titleJa":"日本語タイトル",'
                                    '"summaryJa":["一つ目の文です。","二つ目の文です。","三つ目の文です。"]}]}'
                                )
                            }
                        ]
                    }
                }
            ]
        }

        with patch.object(fetch_feeds, "call_gemini", return_value=response):
            fetch_feeds.enrich_with_gemini(
                news, api_key="key", model="gemini-test", limit_per_category=10, batch_size=5, delay_seconds=0
            )

        item = news["categories"][0]["items"][0]
        self.assertEqual(item["titleJa"], "日本語タイトル")
        self.assertEqual(len(item["summaryJa"]), 3)
        self.assertEqual(item["translationStatus"], "translated")
        self.assertEqual(news["translation"]["translatedItems"], 1)

    def test_enrich_with_gemini_failure_keeps_original_article(self) -> None:
        news = {
            "categories": [
                {
                    "name": "世界ニュース",
                    "items": [{"title": "Original", "excerpt": "Original excerpt", "link": "https://example.com"}],
                }
            ]
        }

        with patch.object(fetch_feeds, "call_gemini", side_effect=ValueError("bad response")):
            fetch_feeds.enrich_with_gemini(
                news, api_key="key", model="gemini-test", limit_per_category=10, batch_size=5, delay_seconds=0
            )

        item = news["categories"][0]["items"][0]
        self.assertEqual(item["title"], "Original")
        self.assertNotIn("titleJa", item)
        self.assertEqual(item["translationStatus"], "failed")
        self.assertEqual(len(news["translation"]["failedBatches"]), 1)


if __name__ == "__main__":
    unittest.main()
