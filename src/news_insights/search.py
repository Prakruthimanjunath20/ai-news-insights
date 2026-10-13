"""Context-aware search over enriched stories.

A query is matched two ways: by the entities it names (a company, ticker, sector or
regulator) and by plain TF-IDF text similarity. When a query names an entity, the
entity match dominates, so "Barclays" ranks a story *about* Barclays above one that
only affects it through the banking sector.
"""

from __future__ import annotations

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from news_insights.catalog import company_by_ticker
from news_insights.enrich.rules import EntityExtractor
from news_insights.models import Entity, EntityKind, SearchHit, StoryInsight

ENTITY_WEIGHT = 0.7
TEXT_WEIGHT = 0.3

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    """Lowercase words without stop words, with a light plural fold ("rates" -> "rate")."""
    words = (w for w in _WORD.findall(text.lower()) if w not in ENGLISH_STOP_WORDS)
    return [w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in words]


def _document(story: StoryInsight) -> str:
    parts = [story.headline, story.headline, story.summary]
    parts += [e.name for e in story.entities]
    parts += [s.ticker for s in story.impacted_stocks if s.confidence >= 1.0]
    return " ".join(parts)


class QueryEngine:
    def __init__(self, insights: list[StoryInsight], extractor: EntityExtractor | None = None):
        self.insights = insights
        self.extractor = extractor or EntityExtractor()
        self._vectorizer: TfidfVectorizer | None = None
        if insights:
            try:
                self._vectorizer = TfidfVectorizer(
                    tokenizer=_tokens,
                    token_pattern=None,
                    lowercase=False,
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                )
                self._matrix = self._vectorizer.fit_transform([_document(s) for s in insights])
            except ValueError:  # every document was stop words
                self._vectorizer = None

    def search(self, query: str, limit: int = 10, min_score: float = 0.05) -> list[SearchHit]:
        query = query.strip()
        if not query or not self.insights:
            return []

        query_entities = self.extractor.extract_from_query(query)
        if self._vectorizer is not None:
            text_scores = cosine_similarity(
                self._vectorizer.transform([query]), self._matrix
            ).ravel()
        else:
            text_scores = [0.0] * len(self.insights)

        hits: list[SearchHit] = []
        for story, text_score in zip(self.insights, text_scores, strict=True):
            entity_score, matched = self._entity_score(story, query_entities)
            text_score = float(text_score)
            if query_entities:
                score = ENTITY_WEIGHT * entity_score + TEXT_WEIGHT * text_score
            else:
                score = text_score
            if text_score > 0.1:
                matched.append("text match")
            if score >= min_score:
                hits.append(SearchHit(story=story, score=round(score, 3), matched=matched))

        hits.sort(key=lambda h: (-h.score, -h.story.last_seen.timestamp()))
        return hits[:limit]

    @staticmethod
    def _entity_score(story: StoryInsight, query_entities: list[Entity]) -> tuple[float, list[str]]:
        mentioned = {(e.kind, e.name) for e in story.entities}
        impacts = {s.ticker: s for s in story.impacted_stocks}
        best = 0.0
        matched: list[str] = []

        for entity in query_entities:
            score = 0.0
            if (entity.kind, entity.name) in mentioned:
                score = 1.0 if entity.kind is not EntityKind.SECTOR else 0.9
                matched.append(f"mentions {entity.name}")
            elif entity.kind is EntityKind.COMPANY and entity.ticker in impacts:
                impact = impacts[entity.ticker]
                score = impact.confidence
                matched.append(f"affects {entity.ticker} via {impact.reason.value}")
            elif entity.kind is EntityKind.SECTOR:
                sector_hits = [
                    s
                    for s in impacts.values()
                    if (company := company_by_ticker(s.ticker)) and company.sector == entity.name
                ]
                if sector_hits:
                    score = 0.7 * max(s.confidence for s in sector_hits)
                    matched.append(f"affects {entity.name} stocks")
            best = max(best, score)

        return best, matched
