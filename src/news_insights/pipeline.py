"""Runs the stages in order (dedup -> enrich -> impact -> index) and holds the results."""

from __future__ import annotations

from collections.abc import Iterable

from news_insights.dedup import DedupConfig, cluster_articles
from news_insights.enrich import Enricher, RuleEnricher
from news_insights.impact import compute_impacts
from news_insights.models import (
    Alert,
    Article,
    SearchHit,
    SentimentLabel,
    StoryInsight,
)
from news_insights.search import QueryEngine

MAX_ENRICH_CHARS = 4000


def build_insights(
    articles: Iterable[Article],
    enricher: Enricher,
    dedup_config: DedupConfig | None = None,
) -> list[StoryInsight]:
    by_id = {a.id: a for a in articles}
    insights: list[StoryInsight] = []
    for story in cluster_articles(list(by_id.values()), dedup_config):
        members = [by_id[i] for i in story.article_ids]
        # Enrich using every article in the story so a company named by only one
        # outlet is still picked up.
        text = "\n".join(a.text for a in members)[:MAX_ENRICH_CHARS]
        enrichment = enricher.enrich(text)
        insights.append(
            StoryInsight(
                **story.model_dump(),
                entities=enrichment.entities,
                sentiment=enrichment.sentiment,
                impacted_stocks=compute_impacts(enrichment.entities, enrichment.sentiment),
                enriched_by=enrichment.enriched_by,
            )
        )
    return insights


class InsightStore:
    """Read-only view over one pipeline run."""

    def __init__(self, insights: list[StoryInsight]) -> None:
        self.insights = insights
        self._by_id = {s.id: s for s in insights}
        self._engine = QueryEngine(insights)

    def __len__(self) -> int:
        return len(self.insights)

    def get(self, story_id: str) -> StoryInsight | None:
        return self._by_id.get(story_id)

    def list_stories(
        self,
        ticker: str | None = None,
        sentiment: SentimentLabel | None = None,
        limit: int = 20,
    ) -> list[StoryInsight]:
        stories = self.insights
        if ticker:
            wanted = ticker.upper()
            stories = [s for s in stories if any(i.ticker == wanted for i in s.impacted_stocks)]
        if sentiment:
            stories = [s for s in stories if s.sentiment.label is sentiment]
        return stories[:limit]

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        return self._engine.search(query, limit=limit)

    def alerts(
        self,
        watchlist: set[str] | None = None,
        min_confidence: float = 0.6,
        min_abs_sentiment: float = 0.3,
    ) -> list[Alert]:
        """Stocks hit by strongly positive or negative stories."""
        watch = {t.upper() for t in watchlist} if watchlist else None
        alerts = [
            Alert(
                story_id=story.id,
                headline=story.headline,
                ticker=impact.ticker,
                company=impact.company,
                direction=story.sentiment.label,
                confidence=impact.confidence,
                sentiment_score=story.sentiment.score,
            )
            for story in self.insights
            if story.sentiment.label is not SentimentLabel.NEUTRAL
            and abs(story.sentiment.score) >= min_abs_sentiment
            for impact in story.impacted_stocks
            if impact.confidence >= min_confidence and (watch is None or impact.ticker in watch)
        ]
        return sorted(alerts, key=lambda a: -a.confidence * abs(a.sentiment_score))


class Pipeline:
    """Keeps every article seen so far and rebuilds insights when new ones arrive."""

    def __init__(
        self,
        enricher: Enricher | None = None,
        dedup_config: DedupConfig | None = None,
    ) -> None:
        self.enricher = enricher or RuleEnricher()
        self.dedup_config = dedup_config
        self.articles: dict[str, Article] = {}
        self.store = InsightStore([])

    def add_articles(self, articles: Iterable[Article]) -> int:
        """Add articles not seen before (by id or URL). Returns how many were new."""
        known_urls = {a.url for a in self.articles.values() if a.url}
        added = 0
        for article in articles:
            if article.id in self.articles or (article.url and article.url in known_urls):
                continue
            self.articles[article.id] = article
            if article.url:
                known_urls.add(article.url)
            added += 1
        return added

    def run(self) -> InsightStore:
        self.store = InsightStore(
            build_insights(self.articles.values(), self.enricher, self.dedup_config)
        )
        return self.store
