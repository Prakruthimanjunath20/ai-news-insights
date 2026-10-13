"""Turns a story's entities and sentiment into a ranked list of affected stocks."""

from __future__ import annotations

from news_insights.catalog import companies_in_sector, company_by_ticker, regulator_by_name
from news_insights.models import Entity, EntityKind, ImpactedStock, ImpactReason, Sentiment

# How confident we are that a stock is affected, by how it is connected to the story.
CONFIDENCE = {
    ImpactReason.DIRECT: 1.0,
    ImpactReason.SECTOR: 0.6,
    ImpactReason.REGULATOR: 0.5,
}


def compute_impacts(entities: list[Entity], sentiment: Sentiment) -> list[ImpactedStock]:
    best: dict[str, ImpactedStock] = {}

    def add(ticker: str, reason: ImpactReason) -> None:
        company = company_by_ticker(ticker)
        if company is None:
            return
        candidate = ImpactedStock(
            ticker=company.ticker,
            company=company.name,
            confidence=CONFIDENCE[reason],
            reason=reason,
            direction=sentiment.label,
        )
        current = best.get(company.ticker)
        if current is None or candidate.confidence > current.confidence:
            best[company.ticker] = candidate

    for entity in entities:
        if entity.kind is EntityKind.COMPANY and entity.ticker:
            add(entity.ticker, ImpactReason.DIRECT)
        elif entity.kind is EntityKind.SECTOR:
            for company in companies_in_sector(entity.name):
                add(company.ticker, ImpactReason.SECTOR)
        elif entity.kind is EntityKind.REGULATOR:
            regulator = regulator_by_name(entity.name)
            for sector in regulator.affects_sectors if regulator else ():
                for company in companies_in_sector(sector):
                    add(company.ticker, ImpactReason.REGULATOR)

    return sorted(best.values(), key=lambda s: (-s.confidence, s.ticker))
