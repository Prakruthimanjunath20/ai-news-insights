"""Fetch live articles from RSS/Atom feeds concurrently."""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

import feedparser
import httpx

from news_insights.models import Article

DEFAULT_FEEDS = (
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.theguardian.com/uk/business/rss",
)

_TAG = re.compile(r"<[^>]+>")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?])")


def _clean(raw: str) -> str:
    # Feeds often escape their HTML, so unescape before stripping tags.
    text = " ".join(_TAG.sub(" ", html.unescape(raw)).split())
    return _SPACE_BEFORE_PUNCT.sub(r"\1", text)


def parse_feed(content: bytes | str, feed_url: str) -> list[Article]:
    parsed = feedparser.parse(content)
    source = parsed.feed.get("title") or urlparse(feed_url).netloc
    articles: list[Article] = []
    for entry in parsed.entries:
        title = _clean(entry.get("title", ""))
        if not title:
            continue
        link = entry.get("link")
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = datetime(*stamp[:6], tzinfo=UTC) if stamp else datetime.now(UTC)
        key = (link or f"{feed_url}|{title}").encode()
        articles.append(
            Article(
                id=f"rss-{hashlib.sha1(key).hexdigest()[:12]}",
                title=title,
                body=_clean(entry.get("summary", "")),
                source=source,
                url=link,
                published_at=published,
            )
        )
    return articles


async def fetch_feed(client: httpx.AsyncClient, url: str) -> list[Article]:
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    return parse_feed(response.content, url)


async def fetch_feeds(
    urls: list[str] | tuple[str, ...] = DEFAULT_FEEDS,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[Article], dict[str, str]]:
    """Fetch every feed at once. Returns the articles plus an error message per failed feed."""
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=15.0, headers={"User-Agent": "ai-news-insights/0.1"}
    )
    try:
        results = await asyncio.gather(
            *(fetch_feed(client, url) for url in urls), return_exceptions=True
        )
    finally:
        if owns_client:
            await client.aclose()

    articles: list[Article] = []
    errors: dict[str, str] = {}
    for url, result in zip(urls, results, strict=True):
        if isinstance(result, BaseException):
            errors[url] = f"{type(result).__name__}: {result}"
        else:
            articles.extend(result)
    return articles, errors
