from news_insights.impact import compute_impacts
from news_insights.models import (
    Entity,
    EntityKind,
    ImpactReason,
    Sentiment,
    SentimentLabel,
)

NEGATIVE = Sentiment(label=SentimentLabel.NEGATIVE, score=-0.6)


def test_direct_mentions_outrank_sector_and_regulator_links():
    impacts = compute_impacts(
        [
            Entity(kind=EntityKind.COMPANY, name="Lloyds Banking Group", ticker="LLOY"),
            Entity(kind=EntityKind.REGULATOR, name="FCA"),
            Entity(kind=EntityKind.SECTOR, name="Banking"),
        ],
        NEGATIVE,
    )
    by_ticker = {i.ticker: i for i in impacts}
    assert impacts[0].ticker == "LLOY"
    assert by_ticker["LLOY"].reason is ImpactReason.DIRECT
    assert by_ticker["BARC"].reason is ImpactReason.SECTOR  # sector (0.6) beats regulator (0.5)
    assert all(i.direction is SentimentLabel.NEGATIVE for i in impacts)


def test_regulator_only_story_reaches_its_sector():
    impacts = compute_impacts([Entity(kind=EntityKind.REGULATOR, name="Ofgem")], NEGATIVE)
    assert {i.ticker for i in impacts} == {"BP", "SHEL"}
    assert {i.confidence for i in impacts} == {0.5}


def test_company_search_prefers_direct_mentions(store):
    hits = store.search("Barclays")
    assert "Barclays" in hits[0].story.headline
    assert "mentions Barclays" in hits[0].matched


def test_ticker_and_theme_queries(store):
    assert "Lloyds" in store.search("LLOY")[0].story.headline
    top_rates = store.search("interest rate impact")[0].story.headline
    assert "Bank of England" in top_rates
    assert "AstraZeneca" in store.search("drug approval")[0].story.headline


def test_blank_query_returns_nothing(store):
    assert store.search("   ") == []


def test_alerts_respect_watchlist(store):
    alerts = store.alerts({"bp"})
    assert alerts and {a.ticker for a in alerts} == {"BP"}
    assert alerts[0].direction is SentimentLabel.NEGATIVE


def test_pipeline_skips_known_articles(pipeline, sample_articles):
    assert pipeline.add_articles(sample_articles) == 0
