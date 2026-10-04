#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_USER_ID = "8b001a3d-0399-48f8-94fe-bf3fbf6e1e05"
DEFAULT_COMMUNITY_ID = "87482a82-23d4-41d2-b867-34810805da02"
DEFAULT_HEADERS = [
    "id",
    "user_id",
    "community_id",
    "title",
    "content",
    "post_type",
    "slug",
    "created_at",
    "updated_at",
    "is_deleted",
    "is_flagged",
    "is_shadow_banned",
    "flagged_reason",
    "like_count",
    "share_count",
    "sector_id",
    "hot_score",
    "status",
    "content_hash",
    "moderated_by",
    "moderated_at",
    "version",
]


class ArticleHTMLToText(HTMLParser):
    BLOCK_TAGS = {"p", "div", "section", "article", "ul", "ol", "table"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.list_depth = 0
        self.in_li = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag == "br":
            self.parts.append("\n")
        elif tag in self.HEADING_TAGS or tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")
        elif tag in {"ul", "ol"}:
            self.list_depth += 1
        elif tag == "li":
            self.in_li = True
            indent = "  " * max(self.list_depth - 1, 0)
            self.parts.append(f"\n{indent}- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
            return

        if self.skip_depth:
            return

        if tag in self.HEADING_TAGS or tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")
        elif tag in {"ul", "ol"} and self.list_depth:
            self.list_depth -= 1
            self.parts.append("\n")
        elif tag == "li":
            self.in_li = False
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        text = html.unescape("".join(self.parts))
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


@dataclass
class ScrapedArticle:
    title: str
    slug: str
    content: str
    published_at: str
    source_url: str


def now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fetch_html(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def extract_next_data(html_text: str) -> dict:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(?P<data>.*?)</script>',
        html_text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ JSON in page")
    return json.loads(match.group("data"))


def html_to_text(article_html: str) -> str:
    parser = ArticleHTMLToText()
    parser.feed(article_html)
    return parser.get_text()


def scrape_article(url: str, timeout: int) -> ScrapedArticle:
    page_html = fetch_html(url, timeout=timeout)
    next_data = extract_next_data(page_html)
    page_props = next_data["props"]["pageProps"]
    article = page_props.get("postDataFromWriteApi")
    if article is None:
        raise ValueError("postDataFromWriteApi is missing or null for this URL")

    title = article["post_title"].strip()
    slug = article["post_slug"].strip()
    article_html = article["post_content"]
    content = html_to_text(article_html)
    published_at = article.get("publish_date", "")

    if not content:
        raise ValueError("Article content was empty after HTML conversion")

    return ScrapedArticle(
        title=title,
        slug=slug,
        content=content,
        published_at=published_at,
        source_url=url,
    )


def read_urls(path: Path) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # ponytail: anything not starting with http (blank, "#" comments, "Company:" labels) is skipped
        if not line.startswith(("http://", "https://")):
            continue
        if line not in seen:
            urls.append(line)
            seen.add(line)
    return urls


def build_row(article: ScrapedArticle, user_id: str, community_id: str) -> dict[str, str]:
    timestamp = now_iso_z()
    content_hash = hashlib.sha256(article.content.encode("utf-8")).hexdigest()
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "community_id": community_id,
        "title": article.title,
        "content": article.content,
        "post_type": "TEXT",
        "slug": article.slug,
        "created_at": timestamp,
        "updated_at": timestamp,
        "is_deleted": "FALSE",
        "is_flagged": "FALSE",
        "is_shadow_banned": "FALSE",
        "flagged_reason": "",
        "like_count": "0",
        "share_count": "0",
        "sector_id": "",
        "hot_score": "",
        "status": "PUBLISHED",
        "content_hash": content_hash,
        "moderated_by": "",
        "moderated_at": "",
        "version": "1",
    }


def resolve_headers(sample_csv: Path | None) -> list[str]:
    if not sample_csv:
        return DEFAULT_HEADERS

    with sample_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise ValueError(f"Sample CSV is empty: {sample_csv}") from exc

    if not headers:
        raise ValueError(f"Sample CSV did not contain headers: {sample_csv}")
    return headers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape GeeksforGeeks interview-experience articles into a posts CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("urls.txt"),
        help="Text file containing one GeeksforGeeks URL per line.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scraped_posts.csv"),
        help="Destination CSV file.",
    )
    parser.add_argument(
        "--sample-csv",
        type=Path,
        default=None,
        help="Optional sample CSV to copy the header order from.",
    )
    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help="user_id to use for every generated row.",
    )
    parser.add_argument(
        "--community-id",
        default=DEFAULT_COMMUNITY_ID,
        help="community_id to use for every generated row.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        print(f"Input URL file not found: {args.input}", file=sys.stderr)
        return 1

    headers = resolve_headers(args.sample_csv)
    urls = read_urls(args.input)
    if not urls:
        print(f"No URLs found in {args.input}", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    failures: list[tuple[str, str]] = []

    for index, url in enumerate(urls, start=1):
        print(f"[{index}/{len(urls)}] Scraping {url}", file=sys.stderr)
        try:
            article = scrape_article(url, timeout=args.timeout)
            rows.append(build_row(article, args.user_id, args.community_id))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
            failures.append((url, str(exc)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")
    if failures:
        print("\nFailed URLs:", file=sys.stderr)
        for url, error in failures:
            print(f"- {url} -> {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
