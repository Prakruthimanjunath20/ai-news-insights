"""Load articles from JSON Lines files, including the bundled sample data."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from news_insights.models import Article


def parse_jsonl(text: str) -> list[Article]:
    return [Article.model_validate(json.loads(line)) for line in text.splitlines() if line.strip()]


def load_jsonl(path: str | Path) -> list[Article]:
    return parse_jsonl(Path(path).read_text(encoding="utf-8"))


def load_sample_articles() -> list[Article]:
    """Synthetic headlines bundled with the package for demos and tests (not real news)."""
    resource = files("news_insights").joinpath("data/sample_articles.jsonl")
    return parse_jsonl(resource.read_text(encoding="utf-8"))
