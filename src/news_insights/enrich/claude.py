"""Optional enrichment with Claude, using tool use to get structured output.

If the API call fails for any reason the story is enriched with the offline rules
instead, so the pipeline never stops because of a network or quota problem.
"""

from __future__ import annotations

import logging
from typing import Any

from news_insights.catalog import COMPANIES, REGULATORS, SECTORS
from news_insights.enrich.rules import EntityExtractor
from news_insights.models import Enrichment, Entity, EntityKind, Sentiment, SentimentLabel

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-5-5"
TOOL_NAME = "record_news_analysis"

_SYSTEM = (
    "You analyse UK financial news for an equity research tool. "
    "Record only what the story states; do not guess at companies that are not mentioned. "
    "Sentiment is the likely effect of the story on the share prices involved, "
    "from -1 (clearly negative) to 1 (clearly positive)."
)


def analysis_tool() -> dict[str, Any]:
    known = ", ".join(c.name for c in COMPANIES)
    return {
        "name": TOOL_NAME,
        "description": "Record the companies, sectors, regulators and sentiment in a news story.",
        "input_schema": {
            "type": "object",
            "properties": {
                "companies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"Companies named in the story. Prefer these names: {known}.",
                },
                "sectors": {
                    "type": "array",
                    "items": {"type": "string", "enum": [s.name for s in SECTORS]},
                },
                "regulators": {
                    "type": "array",
                    "items": {"type": "string", "enum": [r.name for r in REGULATORS]},
                },
                "sentiment_label": {"type": "string", "enum": [s.value for s in SentimentLabel]},
                "sentiment_score": {"type": "number", "minimum": -1, "maximum": 1},
            },
            "required": [
                "companies",
                "sectors",
                "regulators",
                "sentiment_label",
                "sentiment_score",
            ],
        },
    }


class ClaudeEnricher:
    name = "claude"

    def __init__(
        self,
        client: Any | None = None,
        model: str = DEFAULT_MODEL,
        fallback: Any | None = None,
    ) -> None:
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on install
                raise RuntimeError(
                    "Claude enrichment needs the 'llm' extra: pip install 'ai-news-insights[llm]'"
                ) from exc
            client = anthropic.Anthropic()
        if fallback is None:
            from news_insights.enrich import RuleEnricher

            fallback = RuleEnricher()
        self.client = client
        self.model = model
        self.fallback = fallback
        self.fallback_count = 0
        self._matcher = EntityExtractor()

    def enrich(self, text: str) -> Enrichment:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=_SYSTEM,
                tools=[analysis_tool()],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": f"<story>\n{text}\n</story>"}],
            )
            data = next(
                block.input
                for block in response.content
                if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME
            )
            return self._to_enrichment(data)
        except Exception as exc:  # any failure should fall back to rules, not crash
            self.fallback_count += 1
            logger.warning("Claude enrichment failed, using rules instead: %s", exc)
            return self.fallback.enrich(text)

    def _to_enrichment(self, data: dict[str, Any]) -> Enrichment:
        entities: dict[tuple[str, str], Entity] = {}
        for name in data.get("companies", []):
            matches = [
                e for e in self._matcher.extract_from_query(name) if e.kind is EntityKind.COMPANY
            ]
            entity = matches[0] if matches else Entity(kind=EntityKind.COMPANY, name=name)
            entities[(entity.kind, entity.name)] = entity
        known_sectors = {s.name for s in SECTORS}
        for name in data.get("sectors", []):
            if name in known_sectors:
                entities[(EntityKind.SECTOR, name)] = Entity(kind=EntityKind.SECTOR, name=name)
        known_regulators = {r.name for r in REGULATORS}
        for name in data.get("regulators", []):
            if name in known_regulators:
                entities[(EntityKind.REGULATOR, name)] = Entity(
                    kind=EntityKind.REGULATOR, name=name
                )

        score = max(-1.0, min(1.0, float(data["sentiment_score"])))
        return Enrichment(
            entities=list(entities.values()),
            sentiment=Sentiment(label=SentimentLabel(data["sentiment_label"]), score=score),
            enriched_by=self.name,
        )
