"""Built-in skill: market sentiment summary."""

from __future__ import annotations

from typing import Any


class Skill:
    name = "market_sentiment"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        symbol = str(params.get("symbol", "BTCUSDT")).upper()
        score = float(params.get("score", 0.0))
        label = "bullish" if score > 0.2 else "bearish" if score < -0.2 else "neutral"
        return {
            "skill": self.name,
            "symbol": symbol,
            "sentiment": label,
            "score": score,
        }
