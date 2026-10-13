"""Deterministic, offline entity extraction using the reference catalogue."""

from __future__ import annotations

import re
from dataclasses import dataclass

from news_insights.catalog import COMPANIES, REGULATORS, SECTORS
from news_insights.models import Entity, EntityKind


def _phrase_pattern(phrase: str, *, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", flags)


@dataclass(frozen=True)
class _Rule:
    entity: Entity
    article_patterns: tuple[re.Pattern[str], ...]
    query_patterns: tuple[re.Pattern[str], ...]


def _build_rules() -> list[_Rule]:
    rules: list[_Rule] = []
    for company in COMPANIES:
        names = company.all_names
        rules.append(
            _Rule(
                Entity(kind=EntityKind.COMPANY, name=company.name, ticker=company.ticker),
                # Company names are matched case-sensitively in articles so that, for
                # example, "BP" does not fire on "bp" (basis points).
                tuple(_phrase_pattern(n, case_sensitive=True) for n in names),
                tuple(_phrase_pattern(n, case_sensitive=False) for n in (*names, company.ticker)),
            )
        )
    for regulator in REGULATORS:
        rules.append(
            _Rule(
                Entity(kind=EntityKind.REGULATOR, name=regulator.name),
                tuple(_phrase_pattern(a, case_sensitive=True) for a in regulator.aliases),
                tuple(_phrase_pattern(a, case_sensitive=False) for a in regulator.aliases),
            )
        )
    for sector in SECTORS:
        keywords = (sector.name, *sector.keywords)
        patterns = tuple(_phrase_pattern(k, case_sensitive=False) for k in keywords)
        rules.append(_Rule(Entity(kind=EntityKind.SECTOR, name=sector.name), patterns, patterns))
    return rules


_KIND_ORDER = {EntityKind.COMPANY: 0, EntityKind.REGULATOR: 1, EntityKind.SECTOR: 2}


class EntityExtractor:
    """Finds known companies, regulators and sectors in text."""

    def __init__(self) -> None:
        self._rules = _build_rules()

    def extract(self, text: str) -> list[Entity]:
        """Entities mentioned in an article (case-sensitive for names)."""
        return self._match(text, query=False)

    def extract_from_query(self, query: str) -> list[Entity]:
        """Entities in a user's search query (case-insensitive, accepts tickers)."""
        return self._match(query, query=True)

    def _match(self, text: str, *, query: bool) -> list[Entity]:
        found = []
        for rule in self._rules:
            patterns = rule.query_patterns if query else rule.article_patterns
            if any(p.search(text) for p in patterns):
                found.append(rule.entity)
        return sorted(found, key=lambda e: (_KIND_ORDER[e.kind], e.name))
