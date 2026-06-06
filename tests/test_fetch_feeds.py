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


if __name__ == "__main__":
    unittest.main()
