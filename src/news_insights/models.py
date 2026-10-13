"""Typed data models shared by every stage of the pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Article(BaseModel):
    """A single news article as it arrives from a source."""

    id: str
    title: str
    body: str = ""
    source: str
    url: str | None = None
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        # Feeds disagree on time zones; treat naive timestamps as UTC so they compare.
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.body}".strip()


class EntityKind(StrEnum):
    COMPANY = "company"
    SECTOR = "sector"
    REGULATOR = "regulator"


class Entity(BaseModel):
    kind: EntityKind
    name: str
    ticker: str | None = None


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Sentiment(BaseModel):
    label: SentimentLabel
    score: float = Field(ge=-1.0, le=1.0)


class ImpactReason(StrEnum):
    DIRECT = "direct_mention"
    SECTOR = "sector"
    REGULATOR = "regulator"


class ImpactedStock(BaseModel):
    ticker: str
    company: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: ImpactReason
    direction: SentimentLabel


class Enrichment(BaseModel):
    """What an enricher learns from a story's text."""

    entities: list[Entity] = []
    sentiment: Sentiment
    enriched_by: str = "rules"


class Story(BaseModel):
    """A group of articles that report the same event."""

    id: str
    headline: str
    summary: str
    article_ids: list[str]
    sources: list[str]
    first_seen: datetime
    last_seen: datetime


class StoryInsight(Story):
    entities: list[Entity] = []
    sentiment: Sentiment
    impacted_stocks: list[ImpactedStock] = []
    enriched_by: str = "rules"


class SearchHit(BaseModel):
    story: StoryInsight
    score: float
    matched: list[str] = []


class Alert(BaseModel):
    story_id: str
    headline: str
    ticker: str
    company: str
    direction: SentimentLabel
    confidence: float
    sentiment_score: float
