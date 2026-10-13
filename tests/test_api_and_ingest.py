import asyncio

import httpx

from news_insights.ingest import fetch_feeds, parse_feed

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Tesco &amp; Sainsbury&#39;s cut prices</title>
<link>https://example.com/a</link>
<description>&lt;p&gt;Supermarkets cut <b>prices</b>.&lt;/p&gt;</description>
<pubDate>Tue, 06 Oct 2026 08:00:00 GMT</pubDate></item>
<item><title></title><link>https://example.com/empty</link></item>
</channel></rss>"""


def test_parse_feed_cleans_html_and_skips_untitled_items():
    articles = parse_feed(RSS, "https://example.com/feed")
    assert len(articles) == 1
    article = articles[0]
    assert article.title == "Tesco & Sainsbury's cut prices"
    assert article.body == "Supermarkets cut prices."
    assert article.source == "Test Feed"
    assert article.published_at.year == 2026


def test_fetch_feeds_reports_failures_without_stopping():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/good":
            return httpx.Response(200, content=RSS)
        return httpx.Response(503)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_feeds(
                ["https://feeds.test/good", "https://feeds.test/bad"], client=client
            )

    articles, errors = asyncio.run(run())
    assert len(articles) == 1
    assert list(errors) == ["https://feeds.test/bad"]


def test_health_and_index(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["articles"] == 25 and health["stories"] == 15
    page = client.get("/")
    assert page.status_code == 200 and "AI News Insights" in page.text


def test_stories_filters(client):
    negative = client.get("/stories", params={"sentiment": "negative"}).json()
    assert negative and all(s["sentiment"]["label"] == "negative" for s in negative)
    bp = client.get("/stories", params={"ticker": "bp"}).json()
    assert all(any(i["ticker"] == "BP" for i in s["impacted_stocks"]) for s in bp)


def test_story_lookup_and_404(client):
    story_id = client.get("/stories", params={"limit": 1}).json()[0]["id"]
    assert client.get(f"/stories/{story_id}").json()["id"] == story_id
    assert client.get("/stories/story-missing").status_code == 404


def test_search_endpoint_validates_input(client):
    assert client.get("/search", params={"q": "Barclays"}).json()[0]["score"] > 0.5
    assert client.get("/search", params={"q": ""}).status_code == 422


def test_company_endpoints(client):
    assert any(c["ticker"] == "AZN" for c in client.get("/companies").json())
    assert client.get("/companies/AZN/stories").status_code == 200
    assert client.get("/companies/NOPE/stories").status_code == 404


def test_alerts_endpoint(client):
    alerts = client.get("/alerts", params={"watchlist": "BARC, RR"}).json()
    assert {a["ticker"] for a in alerts} == {"BARC", "RR"}
