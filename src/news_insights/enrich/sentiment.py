"""A small finance-specific sentiment lexicon.

Generic sentiment models misread market language ("cuts costs" is good news,
"cuts guidance" is bad), so this scorer uses phrases first and single words second,
and flips a word when it follows a negator ("not", "no", "fails to").
"""

from __future__ import annotations

import re

from news_insights.models import Sentiment, SentimentLabel

# Phrase weights are checked before single words; a matched phrase is removed from
# the text so its words are not counted twice.
_PHRASES: dict[str, float] = {
    "profit warning": -2.0,
    "cuts guidance": -2.0,
    "lowers guidance": -2.0,
    "job cuts": -1.5,
    "raises guidance": 2.0,
    "upgrades guidance": 2.0,
    "cuts costs": 1.0,
    "share buyback": 1.5,
    "record profit": 2.0,
    "better than expected": 1.5,
    "worse than expected": -1.5,
    "beats expectations": 1.5,
    "misses expectations": -1.5,
}

# fmt: off
_POSITIVE = {
    "beat", "beats", "record", "surge", "surges", "soar", "soars", "jump", "jumps",
    "rise", "rises", "rising", "gain", "gains", "rally", "rallies", "boost", "boosts",
    "growth", "grows", "strong", "stronger", "upgrade", "upgraded", "approval",
    "approved", "approves", "win", "wins", "won", "dividend", "buyback", "expands",
    "expansion", "recovery", "recovers", "outperform", "outperforms", "resilient", "robust",
}

_NEGATIVE = {
    "fall", "falls", "fell", "drop", "drops", "plunge", "plunges", "slump", "slumps",
    "sink", "sinks", "slide", "slides", "warn", "warns", "warned", "warning", "fine", "fined",
    "fears", "squeeze", "weaken", "weakens",
    "probe", "investigation", "lawsuit", "loss", "losses", "miss", "misses", "downgrade",
    "downgraded", "layoffs", "redundancies", "strike", "strikes", "recall", "outage",
    "breach", "penalty", "delay", "delays", "delayed", "scandal", "weak", "weaker",
    "slowdown", "default", "fraud", "halts", "suspends", "rejects", "rejected",
}

_NEGATORS = {"not", "no", "never", "without", "fails", "failed"}
# fmt: on

_TOKEN = re.compile(r"[a-z0-9']+")
_THRESHOLD = 0.15


def score_sentiment(text: str) -> Sentiment:
    lowered = text.lower()
    total = 0.0

    for phrase, weight in _PHRASES.items():
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
        hits = len(pattern.findall(lowered))
        if hits:
            total += weight * hits
            lowered = pattern.sub(" ", lowered)

    tokens = _TOKEN.findall(lowered)
    for i, token in enumerate(tokens):
        polarity = 1.0 if token in _POSITIVE else -1.0 if token in _NEGATIVE else 0.0
        if polarity and any(t in _NEGATORS for t in tokens[max(0, i - 2) : i]):
            polarity = -polarity
        total += polarity

    # Squash an unbounded total into (-1, 1); 2.0 controls how quickly it saturates.
    score = round(total / (abs(total) + 2.0), 3)
    if score > _THRESHOLD:
        label = SentimentLabel.POSITIVE
    elif score < -_THRESHOLD:
        label = SentimentLabel.NEGATIVE
    else:
        label = SentimentLabel.NEUTRAL
    return Sentiment(label=label, score=score)
