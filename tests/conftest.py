from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from news_insights.api import create_app
from news_insights.ingest import load_sample_articles
from news_insights.models import Article
from news_insights.pipeline import InsightStore, Pipeline


def make_article(id: str, title: str, body: str = "", hours: float = 0, source: str = "Test"):
    return Article(
        id=id,
        title=title,
        body=body,
        source=source,
        published_at=datetime(2026, 9, 1, tzinfo=UTC) + timedelta(hours=hours),
    )


@pytest.fixture(scope="session")
def sample_articles() -> list[Article]:
    return load_sample_articles()


@pytest.fixture()
def pipeline(sample_articles) -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_articles(sample_articles)
    pipeline.run()
    return pipeline


@pytest.fixture()
def store(pipeline) -> InsightStore:
    return pipeline.store


@pytest.fixture()
def client(pipeline) -> TestClient:
    return TestClient(create_app(pipeline))
