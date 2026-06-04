from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "scripts" / "feeds.json"
DEFAULT_OUTPUT = ROOT / "news.json"
MAX_ITEMS_PER_CATEGORY = 30
REQUEST_TIMEOUT_SECONDS = 20

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def text_or_empty(value: str | None) -> str:
    if not value:
        return ""
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", value))).strip()


def truncate(text: str, limit: int = 140) -> str:
    text = text_or_empty(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def child_text(element: ElementTree.Element, names: tuple[str, ...]) -> str:
    names = tuple(name.rsplit(":", 1)[-1].lower() for name in names)
    for child in element.iter():
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name in names and child.text:
            return text_or_empty(child.text)
    return ""


def atom_link(element: ElementTree.Element) -> str:
    for child in element.iter():
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name == "link":
            href = child.attrib.get("href")
            rel = child.attrib.get("rel", "alternate")
            if href and rel == "alternate":
                return href.strip()
            if child.text:
                return child.text.strip()
    return ""


def parse_date(value: str) -> tuple[str, float]:
    value = text_or_empty(value)
    if not value:
        return "", 0

    parsers = (
        email.utils.parsedate_to_datetime,
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")),
    )
    for parser in parsers:
        try:
            parsed = parser(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(timezone.utc)
            return parsed.isoformat().replace("+00:00", "Z"), parsed.timestamp()
        except (TypeError, ValueError, IndexError, AttributeError):
            continue
    return value, 0


def fetch_xml(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "StaticRSSNewsBot/1.0 (+https://github.com/)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}:
            raise ValueError(f"unexpected content type: {content_type}")
        return response.read()


def safe_link(value: str) -> str:
    value = value.strip()
    parsed = urllib.parse.urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def parse_feed(feed: dict[str, str]) -> list[dict[str, Any]]:
    xml_bytes = fetch_xml(feed["url"])
    root = ElementTree.fromstring(xml_bytes)
    root_name = root.tag.rsplit("}", 1)[-1].lower()
    entries = root.findall(".//item") if root_name == "rss" else root.findall(".//{*}entry")
    if not entries:
        entries = root.findall(".//item") + root.findall(".//{*}entry")

    items: list[dict[str, Any]] = []
    for entry in entries:
        title = child_text(entry, ("title",))
        link = safe_link(child_text(entry, ("link",)) or atom_link(entry))
        published_raw = child_text(entry, ("pubdate", "published", "updated", "dc:date"))
        description = child_text(entry, ("description", "summary", "content", "encoded"))
        published_at, sort_time = parse_date(published_raw)
        if title and link:
            items.append(
                {
                    "title": title,
                    "source": feed["name"],
                    "publishedAt": published_at,
                    "excerpt": truncate(description),
                    "link": link,
                    "_sortTime": sort_time,
                }
            )
    return items


def build_news(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    categories = []
    errors = []

    for category in config["categories"]:
        seen = set()
        items = []
        for feed in category["feeds"]:
            try:
                for item in parse_feed(feed):
                    key = (item["link"].split("?", 1)[0], item["title"].lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(item)
            except (urllib.error.URLError, ElementTree.ParseError, TimeoutError, OSError, ValueError) as exc:
                errors.append(
                    {
                        "category": category["name"],
                        "source": feed["name"],
                        "url": feed["url"],
                        "error": str(exc),
                    }
                )

        items.sort(key=lambda item: item["_sortTime"], reverse=True)
        for item in items:
            item.pop("_sortTime", None)

        categories.append(
            {
                "id": category["id"],
                "name": category["name"],
                "items": items[:MAX_ITEMS_PER_CATEGORY],
            }
        )

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "categories": categories,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch RSS feeds and write static news JSON.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    news = build_news(args.config)
    item_count = sum(len(category["items"]) for category in news["categories"])
    error_count = len(news["errors"])
    if item_count == 0:
        print("No items were fetched; keeping the existing output unchanged.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary_output.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_output.replace(args.output)

    print(f"Wrote {item_count} items to {args.output}")
    if error_count:
        print(f"{error_count} feed(s) failed; site will still publish available items.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
