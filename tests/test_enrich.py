from types import SimpleNamespace

from news_insights.enrich import EntityExtractor, RuleEnricher, make_enricher, score_sentiment
from news_insights.enrich.claude import TOOL_NAME, ClaudeEnricher
from news_insights.models import EntityKind, SentimentLabel


def names(entities):
    return {(e.kind, e.name) for e in entities}


def test_extracts_companies_regulators_and_sectors():
    entities = EntityExtractor().extract("The FCA fined Lloyds, a blow for UK banks.")
    assert names(entities) == {
        (EntityKind.COMPANY, "Lloyds Banking Group"),
        (EntityKind.REGULATOR, "FCA"),
        (EntityKind.SECTOR, "Banking"),
    }
    lloyds = next(e for e in entities if e.kind is EntityKind.COMPANY)
    assert lloyds.ticker == "LLOY"


def test_short_names_are_case_sensitive_in_articles():
    # "bp" here means basis points, not the oil company.
    assert EntityExtractor().extract("Gilt yields rose 10 bp on the day") == []


def test_queries_accept_lowercase_and_tickers():
    extractor = EntityExtractor()
    assert names(extractor.extract_from_query("barc")) == {(EntityKind.COMPANY, "Barclays")}
    assert (EntityKind.COMPANY, "BP") in names(extractor.extract_from_query("bp news"))


def test_sentiment_phrases_and_negation():
    assert score_sentiment("BP issues profit warning").label is SentimentLabel.NEGATIVE
    assert score_sentiment("Shell raises dividend and buyback").label is SentimentLabel.POSITIVE
    assert score_sentiment("Results were not strong").score < 0
    assert score_sentiment("The company held its annual meeting").label is SentimentLabel.NEUTRAL


def test_rule_enricher_reports_its_name():
    assert RuleEnricher().enrich("Barclays shares jump").enriched_by == "rules"
    assert make_enricher("rules").name == "rules"


class FakeMessages:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input=self.payload)
        return SimpleNamespace(content=[block])


def test_claude_enricher_maps_tool_output_to_catalogue():
    messages = FakeMessages(
        {
            "companies": ["Barclays", "Some Private Firm"],
            "sectors": ["Banking", "Not A Sector"],
            "regulators": ["FCA"],
            "sentiment_label": "positive",
            "sentiment_score": 0.8,
        }
    )
    enricher = ClaudeEnricher(client=SimpleNamespace(messages=messages), model="test-model")
    result = enricher.enrich("Barclays ...")

    assert result.enriched_by == "claude"
    assert result.sentiment.score == 0.8
    by_name = {e.name: e for e in result.entities}
    assert by_name["Barclays"].ticker == "BARC"
    assert by_name["Some Private Firm"].ticker is None
    assert "Not A Sector" not in by_name
    call = messages.calls[0]
    assert call["model"] == "test-model"
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}


def test_claude_enricher_falls_back_to_rules_on_error():
    messages = FakeMessages(error=RuntimeError("network down"))
    enricher = ClaudeEnricher(client=SimpleNamespace(messages=messages))
    result = enricher.enrich("BP issues profit warning")

    assert result.enriched_by == "rules"
    assert result.sentiment.label is SentimentLabel.NEGATIVE
    assert enricher.fallback_count == 1
