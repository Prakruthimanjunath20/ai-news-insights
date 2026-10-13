"""Groups articles that report the same event into a single story.

Each article becomes a TF-IDF vector of character n-grams (title counted twice,
because headlines carry most of the signal). Character n-grams cope with the way
outlets reword the same event ("holds"/"held", "buyback"/"buy-back") better than
whole words: on the sample data, true duplicates score 0.38 or more and different
stories 0.21 or less. Two articles are linked when their cosine similarity passes a
threshold *and* they were published within a time window, so a recurring headline
such as "Bank of England holds rates" in March is not merged with the one in June.
Linked articles are grouped with union-find, which makes grouping transitive.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from news_insights.models import Article, Story


@dataclass(frozen=True)
class DedupConfig:
    similarity_threshold: float = 0.30
    window: timedelta = timedelta(hours=72)
    summary_chars: int = 320


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[max(root_a, root_b)] = min(root_a, root_b)


def _story_id(article_ids: list[str]) -> str:
    digest = hashlib.sha1("|".join(sorted(article_ids)).encode()).hexdigest()
    return f"story-{digest[:10]}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def cluster_articles(articles: list[Article], config: DedupConfig | None = None) -> list[Story]:
    """Return one Story per group of duplicate articles, newest first."""
    config = config or DedupConfig()
    if not articles:
        return []

    articles = sorted(articles, key=lambda a: (a.published_at, a.id))
    texts = [f"{a.title} {a.title} {a.body}" for a in articles]
    matrix = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
    ).fit_transform(texts)
    similarity = cosine_similarity(matrix)

    groups = _UnionFind(len(articles))
    rows, cols = np.where(np.triu(similarity, k=1) >= config.similarity_threshold)
    for i, j in zip(rows.tolist(), cols.tolist(), strict=True):
        if abs(articles[i].published_at - articles[j].published_at) <= config.window:
            groups.union(i, j)

    members: dict[int, list[int]] = {}
    for index in range(len(articles)):
        members.setdefault(groups.find(index), []).append(index)

    stories: list[Story] = []
    for indexes in members.values():
        # The representative is the article most similar to the rest of its group.
        sub = similarity[np.ix_(indexes, indexes)]
        representative = articles[indexes[int(sub.sum(axis=1).argmax())]]
        group = [articles[i] for i in indexes]
        ids = [a.id for a in group]
        summary = representative.body or representative.title
        stories.append(
            Story(
                id=_story_id(ids),
                headline=representative.title,
                summary=_truncate(summary, config.summary_chars),
                article_ids=ids,
                sources=list(dict.fromkeys(a.source for a in group)),
                first_seen=min(a.published_at for a in group),
                last_seen=max(a.published_at for a in group),
            )
        )
    return sorted(stories, key=lambda s: (s.last_seen, s.id), reverse=True)
