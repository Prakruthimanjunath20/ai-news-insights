"""Enrichers turn story text into entities and sentiment."""

from __future__ import annotations

import os
from typing import Protocol

from news_insights.enrich.rules import EntityExtractor
from news_insights.enrich.sentiment import score_sentiment
from news_insights.models import Enrichment


class Enricher(Protocol):
    name: str

    def enrich(self, text: str) -> Enrichment: ...


class RuleEnricher:
    """Offline and deterministic: catalogue matching plus a finance sentiment lexicon."""

    name = "rules"

    def __init__(self) -> None:
        self._extractor = EntityExtractor()

    def enrich(self, text: str) -> Enrichment:
        return Enrichment(
            entities=self._extractor.extract(text),
            sentiment=score_sentiment(text),
            enriched_by=self.name,
        )


def make_enricher(kind: str | None = None) -> Enricher:
    """Pick an enricher from the argument or the NEWS_INSIGHTS_ENRICHER variable."""
    kind = (kind or os.environ.get("NEWS_INSIGHTS_ENRICHER", "rules")).lower()
    if kind == "rules":
        return RuleEnricher()
    if kind == "claude":
        from news_insights.enrich.claude import DEFAULT_MODEL, ClaudeEnricher

        return ClaudeEnricher(model=os.environ.get("NEWS_INSIGHTS_MODEL", DEFAULT_MODEL))
    raise ValueError(f"Unknown enricher {kind!r}; use 'rules' or 'claude'")


__all__ = ["Enricher", "EntityExtractor", "RuleEnricher", "make_enricher", "score_sentiment"]
