"""FastAPI service over the insight pipeline."""

from __future__ import annotations

import os
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from news_insights import __version__
from news_insights.catalog import COMPANIES, company_by_ticker
from news_insights.enrich import make_enricher
from news_insights.ingest import DEFAULT_FEEDS, fetch_feeds, load_jsonl, load_sample_articles
from news_insights.models import Alert, SearchHit, SentimentLabel, StoryInsight
from news_insights.pipeline import Pipeline


class Health(BaseModel):
    status: str
    version: str
    articles: int
    stories: int
    enricher: str


class CompanyOut(BaseModel):
    ticker: str
    name: str
    sector: str


class IngestRequest(BaseModel):
    feeds: list[str] | None = None


class IngestResult(BaseModel):
    added: int
    stories: int
    errors: dict[str, str]


def default_pipeline() -> Pipeline:
    pipeline = Pipeline(enricher=make_enricher())
    data_path = os.environ.get("NEWS_INSIGHTS_DATA")
    pipeline.add_articles(load_jsonl(data_path) if data_path else load_sample_articles())
    pipeline.run()
    return pipeline


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    pipeline = pipeline or default_pipeline()
    app = FastAPI(
        title="AI News Insights",
        version=__version__,
        description="Deduplicated financial news stories with entities, sentiment and impact.",
    )
    app.state.pipeline = pipeline

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return files("news_insights").joinpath("static/index.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> Health:
        return Health(
            status="ok",
            version=__version__,
            articles=len(pipeline.articles),
            stories=len(pipeline.store),
            enricher=pipeline.enricher.name,
        )

    @app.get("/stories")
    def list_stories(
        ticker: str | None = None,
        sentiment: SentimentLabel | None = None,
        limit: int = Query(20, ge=1, le=100),
    ) -> list[StoryInsight]:
        return pipeline.store.list_stories(ticker=ticker, sentiment=sentiment, limit=limit)

    @app.get("/stories/{story_id}")
    def get_story(story_id: str) -> StoryInsight:
        story = pipeline.store.get(story_id)
        if story is None:
            raise HTTPException(status_code=404, detail=f"No story with id {story_id!r}")
        return story

    @app.get("/search")
    def search(
        q: str = Query(..., min_length=1, max_length=200),
        limit: int = Query(10, ge=1, le=50),
    ) -> list[SearchHit]:
        return pipeline.store.search(q, limit=limit)

    @app.get("/companies")
    def companies() -> list[CompanyOut]:
        return [CompanyOut(ticker=c.ticker, name=c.name, sector=c.sector) for c in COMPANIES]

    @app.get("/companies/{ticker}/stories")
    def company_stories(ticker: str, limit: int = Query(20, ge=1, le=100)) -> list[StoryInsight]:
        if company_by_ticker(ticker) is None:
            raise HTTPException(status_code=404, detail=f"Unknown ticker {ticker!r}")
        return pipeline.store.list_stories(ticker=ticker, limit=limit)

    @app.get("/alerts")
    def alerts(
        watchlist: str | None = Query(None, description="Comma-separated tickers, e.g. BARC,BP"),
        min_confidence: float = Query(0.6, ge=0, le=1),
        min_abs_sentiment: float = Query(0.3, ge=0, le=1),
    ) -> list[Alert]:
        tickers = {t.strip() for t in watchlist.split(",") if t.strip()} if watchlist else None
        return pipeline.store.alerts(tickers, min_confidence, min_abs_sentiment)

    @app.post("/ingest/rss")
    async def ingest_rss(request: IngestRequest | None = None) -> IngestResult:
        feeds = (request.feeds if request and request.feeds else None) or list(DEFAULT_FEEDS)
        articles, errors = await fetch_feeds(feeds)
        added = pipeline.add_articles(articles)
        if added:
            pipeline.run()
        return IngestResult(added=added, stories=len(pipeline.store), errors=errors)

    return app
