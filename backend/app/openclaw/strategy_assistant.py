"""Conversational strategy creation, code generation, and backtest analysis."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .command_executor import CommandExecutor
from .kimi_k2_client import KimiK2Client
from .logging import StructuredLogger


@dataclass(slots=True)
class StrategySpec:
    name: str
    user_id: str
    description: str
    trading_style: str = "momentum"
    entry_conditions: list[str] = field(default_factory=list)
    exit_conditions: list[str] = field(default_factory=list)
    risk_rules: list[str] = field(default_factory=list)
    timeframe: str = "1h"
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "user_id": self.user_id,
            "description": self.description,
            "trading_style": self.trading_style,
            "entry_conditions": self.entry_conditions,
            "exit_conditions": self.exit_conditions,
            "risk_rules": self.risk_rules,
            "timeframe": self.timeframe,
            "symbols": self.symbols,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StrategySpec:
        return cls(
            name=str(payload.get("name", "strategy")),
            user_id=str(payload.get("user_id", "")),
            description=str(payload.get("description", "")),
            trading_style=str(payload.get("trading_style", "momentum")),
            entry_conditions=list(payload.get("entry_conditions", [])),
            exit_conditions=list(payload.get("exit_conditions", [])),
            risk_rules=list(payload.get("risk_rules", [])),
            timeframe=str(payload.get("timeframe", "1h")),
            symbols=list(payload.get("symbols", ["BTCUSDT"])),
        )


class StrategyAssistant:
    """Guides users through strategy generation and iterative improvement."""

    def __init__(
        self,
        *,
        kimi_client: KimiK2Client,
        command_executor: CommandExecutor,
        strategies_dir: str = "backend/app/openclaw/strategies",
        logger: StructuredLogger | None = None,
    ):
        self._kimi_client = kimi_client
        self._executor = command_executor
        self._strategies_dir = Path(strategies_dir)
        self._strategies_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger or StructuredLogger("openclaw.strategy_assistant")

    async def create_strategy(self, user_id: str, description: str) -> StrategySpec:
        name = (
            description.lower()
            .replace("strategy", "")
            .replace(" ", "_")
            .replace("-", "_")
            .strip("_")
            or "custom_strategy"
        )
        spec = StrategySpec(
            name=name,
            user_id=user_id,
            description=description,
            entry_conditions=["price closes above EMA(20)"],
            exit_conditions=["price closes below EMA(20)"],
            risk_rules=["stoploss 3%", "max 2 open trades"],
        )
        await self.save_strategy_spec(spec)
        return spec

    async def generate_code(self, strategy_spec: StrategySpec) -> str:
        prompt = (
            "Generate freqtrade strategy python code with class name "
            f"{strategy_spec.name.title().replace('_', '')}Strategy. "
            "Include populate_indicators, populate_entry_trend, populate_exit_trend."
        )
        try:
            generated = await self._kimi_client.complete([{"role": "user", "content": prompt}])
            code = self._extract_python(generated)
        except Exception:
            code = self._fallback_code(strategy_spec)

        self._validate_python_syntax(code)
        path = self._strategies_dir / f"{strategy_spec.name}.py"
        path.write_text(code, encoding="utf-8")
        return code

    async def run_backtest(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        symbols: list[str],
    ) -> dict[str, Any]:
        command_payload = {
            "strategy_name": strategy_name,
            "start_date": start_date,
            "end_date": end_date,
            "symbols": symbols,
        }
        result = await self._executor._api_client.run_backtest(command_payload)  # noqa: SLF001
        return result

    def analyze_results(self, backtest_results: dict[str, Any]) -> str:
        total_return = backtest_results.get("total_return", 0.0)
        sharpe = backtest_results.get("sharpe_ratio", 0.0)
        drawdown = backtest_results.get("max_drawdown", 0.0)
        win_rate = backtest_results.get("win_rate", 0.0)
        verdict = "promising" if total_return > 0 and sharpe > 1 else "needs improvement"
        return (
            f"Backtest summary: return={total_return}, sharpe={sharpe}, "
            f"drawdown={drawdown}, win_rate={win_rate}. Strategy is {verdict}."
        )

    def suggest_improvements(self, backtest_results: dict[str, Any]) -> list[str]:
        suggestions: list[str] = []
        if backtest_results.get("sharpe_ratio", 0.0) < 1.0:
            suggestions.append("Tighten entry filters to reduce low-quality trades.")
        if backtest_results.get("max_drawdown", 0.0) > 0.2:
            suggestions.append("Add stricter stop-loss and position sizing constraints.")
        if backtest_results.get("win_rate", 0.0) < 0.45:
            suggestions.append("Refine exit logic to avoid premature stop-outs.")
        if not suggestions:
            suggestions.append("Run walk-forward validation and multi-symbol stress tests.")
        return suggestions

    async def save_strategy_spec(self, spec: StrategySpec) -> Path:
        path = self._strategies_dir / f"{spec.name}.json"
        path.write_text(json.dumps(spec.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
        self._logger.info("Strategy spec saved", {"strategy_name": spec.name, "path": str(path)})
        return path

    def list_strategies(self) -> list[str]:
        return sorted(path.stem for path in self._strategies_dir.glob("*.json"))

    def load_strategy_spec(self, strategy_name: str) -> StrategySpec:
        path = self._strategies_dir / f"{strategy_name}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StrategySpec.from_dict(payload)

    @staticmethod
    def _extract_python(generated_text: str) -> str:
        if "```python" in generated_text:
            start = generated_text.find("```python") + len("```python")
            end = generated_text.find("```", start)
            if end > start:
                return generated_text[start:end].strip()
        return generated_text.strip()

    @staticmethod
    def _validate_python_syntax(code: str) -> None:
        ast.parse(code)

    @staticmethod
    def _fallback_code(spec: StrategySpec) -> str:
        class_name = spec.name.title().replace("_", "") + "Strategy"
        return (
            "from pandas import DataFrame\n\n"
            f"class {class_name}:\n"
            '    minimal_roi = {"0": 0.02}\n'
            "    stoploss = -0.03\n\n"
            "    def populate_indicators(\n"
            "        self, dataframe: DataFrame, metadata: dict\n"
            "    ) -> DataFrame:\n"
            "        dataframe['ema20'] = dataframe['close'].ewm(span=20, adjust=False).mean()\n"
            "        return dataframe\n\n"
            "    def populate_entry_trend(\n"
            "        self, dataframe: DataFrame, metadata: dict\n"
            "    ) -> DataFrame:\n"
            "        dataframe['enter_long'] = dataframe['close'] > dataframe['ema20']\n"
            "        return dataframe\n\n"
            "    def populate_exit_trend(\n"
            "        self, dataframe: DataFrame, metadata: dict\n"
            "    ) -> DataFrame:\n"
            "        dataframe['exit_long'] = dataframe['close'] < dataframe['ema20']\n"
            "        return dataframe\n"
        )
