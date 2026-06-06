from __future__ import annotations

import argparse
import email.utils
import html
import json
import os
import re
import sys
import time
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
GEMINI_TIMEOUT_SECONDS = 40
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_TRANSLATION_LIMIT_PER_CATEGORY = 30
DEFAULT_TRANSLATION_BATCH_SIZE = 5
DEFAULT_TRANSLATION_DELAY_SECONDS = 8
GEMINI_MAX_RETRIES = 3

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


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


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return max(0, int(value))
    except ValueError:
        return default


def build_translation_prompt(category_name: str, items: list[dict[str, Any]]) -> str:
    compact_items = [
        {
            "index": index,
            "title": item["title"],
            "excerpt": item.get("excerpt", ""),
            "source": item.get("source", ""),
        }
        for index, item in enumerate(items)
    ]
    return (
        "次のニュース記事を日本語にしてください。\n"
        "条件:\n"
        "- titleJa は自然な日本語タイトルにする\n"
        "- summaryJa は読みやすい日本語の3〜5行にする\n"
        "- 専門用語は必要に応じて短く補足する\n"
        "- 事実を足さない。RSSのtitleとexcerptから分かる範囲だけを書く\n"
        "- 必ずJSONだけを返す\n"
        '形式: {"items":[{"index":0,"titleJa":"...","summaryJa":["...","...","..."]}]}\n'
        f"カテゴリ: {category_name}\n"
        f"記事: {json.dumps(compact_items, ensure_ascii=False)}"
    )


def extract_response_text(response: dict[str, Any]) -> str:
    parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


def parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty Gemini response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(text)
        if not match:
            raise
        return json.loads(match.group(0))


def call_gemini_once(prompt: str, api_key: str, model: str) -> dict[str, Any]:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    request_body = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "あなたはニュースをやさしい日本語にする編集者です。"
                        "一般読者に伝わる自然な日本語で、事実だけを簡潔にまとめます。"
                    )
                }
            ]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def call_gemini(prompt: str, api_key: str, model: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            return call_gemini_once(prompt, api_key, model)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = exc.headers.get("Retry-After")
            wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 10 * (attempt + 1)
            print(f"Gemini returned HTTP {exc.code}; retrying in {wait_seconds}s.", file=sys.stderr)
            time.sleep(wait_seconds)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            wait_seconds = 10 * (attempt + 1)
            print(f"Gemini request failed; retrying in {wait_seconds}s: {exc}", file=sys.stderr)
            time.sleep(wait_seconds)
    if last_error:
        raise last_error
    raise RuntimeError("Gemini request failed")


def normalize_summary(value: Any) -> list[str]:
    if isinstance(value, str):
        lines = [line.strip(" ・-") for line in value.splitlines()]
    elif isinstance(value, list):
        lines = [text_or_empty(str(line)) for line in value]
    else:
        lines = []
    lines = [line for line in lines if line]
    return lines[:5]


def apply_translation(item: dict[str, Any], translated: dict[str, Any]) -> bool:
    title_ja = text_or_empty(str(translated.get("titleJa", "")))
    summary_ja = normalize_summary(translated.get("summaryJa"))
    if not title_ja or len(summary_ja) < 3:
        return False
    item["titleJa"] = title_ja
    item["summaryJa"] = summary_ja
    item["translationStatus"] = "translated"
    return True


def enrich_with_gemini(
    news: dict[str, Any],
    *,
    api_key: str | None,
    model: str,
    limit_per_category: int,
    batch_size: int,
    delay_seconds: int,
) -> None:
    batch_size = max(1, batch_size)
    delay_seconds = max(0, delay_seconds)
    news["translation"] = {
        "provider": "gemini",
        "model": model,
        "enabled": bool(api_key and limit_per_category),
        "limitPerCategory": limit_per_category,
        "batchSize": batch_size,
        "delaySeconds": delay_seconds,
        "translatedItems": 0,
        "failedBatches": [],
    }
    if not api_key or limit_per_category <= 0:
        for category in news["categories"]:
            for item in category["items"]:
                item.setdefault("translationStatus", "not_configured")
        return

    for category in news["categories"]:
        candidates = category["items"][:limit_per_category]
        if not candidates:
            continue
        translated_before = news["translation"]["translatedItems"]
        for item in candidates:
            item["translationStatus"] = "pending"
        for start in range(0, len(candidates), batch_size):
            batch = candidates[start : start + batch_size]
            if start and delay_seconds:
                time.sleep(delay_seconds)
            try:
                prompt = build_translation_prompt(category["name"], batch)
                response = call_gemini(prompt, api_key, model)
                payload = parse_json_response(extract_response_text(response))
                translated_items = payload.get("items", [])
                if not isinstance(translated_items, list):
                    raise ValueError("Gemini response does not contain an items array")

                by_index = {entry.get("index"): entry for entry in translated_items if isinstance(entry, dict)}
                for index, item in enumerate(batch):
                    if apply_translation(item, by_index.get(index, {})):
                        news["translation"]["translatedItems"] += 1
                    else:
                        item["translationStatus"] = "failed"
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                news["translation"]["failedBatches"].append(
                    {
                        "category": category["name"],
                        "start": start,
                        "count": len(batch),
                        "error": str(exc),
                    }
                )
                for item in batch:
                    item["translationStatus"] = "failed"

        for item in category["items"][limit_per_category:]:
            item.setdefault("translationStatus", "not_requested")
        translated_after = news["translation"]["translatedItems"]
        print(
            f"Translated {translated_after - translated_before}/{len(candidates)} item(s) in {category['name']}."
        )


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
    parser.add_argument("--gemini-model", default=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))
    parser.add_argument(
        "--translation-limit-per-category",
        type=int,
        default=env_int("TRANSLATION_LIMIT_PER_CATEGORY", DEFAULT_TRANSLATION_LIMIT_PER_CATEGORY),
    )
    parser.add_argument(
        "--translation-batch-size",
        type=int,
        default=env_int("TRANSLATION_BATCH_SIZE", DEFAULT_TRANSLATION_BATCH_SIZE),
    )
    parser.add_argument(
        "--translation-delay-seconds",
        type=int,
        default=env_int("TRANSLATION_DELAY_SECONDS", DEFAULT_TRANSLATION_DELAY_SECONDS),
    )
    args = parser.parse_args()

    news = build_news(args.config)
    enrich_with_gemini(
        news,
        api_key=os.environ.get("GEMINI_API_KEY"),
        model=args.gemini_model,
        limit_per_category=args.translation_limit_per_category,
        batch_size=args.translation_batch_size,
        delay_seconds=args.translation_delay_seconds,
    )
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
    translated_count = news.get("translation", {}).get("translatedItems", 0)
    if translated_count:
        print(f"Added Japanese summaries for {translated_count} item(s).")
    elif not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set; published RSS text without translation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
