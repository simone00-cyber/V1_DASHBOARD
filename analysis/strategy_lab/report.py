from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import json


def strategy_report_payload(name: str, ticker: str, period: str, specification: dict[str, Any], metrics: dict[str, Any], data_provider: str = "Yahoo Finance") -> dict[str, Any]:
    return {
        "report_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_name": name,
        "ticker": ticker,
        "test_period": period,
        "data_provider": data_provider,
        "adjusted_prices": True,
        "strategy_definition": specification,
        "performance": metrics,
        "reproducibility": {
            "signal_timing": specification.get("execution", "Next open"),
            "commission_bps": specification.get("commission_bps", 0.0),
            "slippage_bps": specification.get("slippage_bps", 0.0),
            "initial_capital": specification.get("initial_capital", 100000.0),
            "position_fraction": specification.get("position_fraction", 1.0),
        },
    }


def strategy_report_text(payload: dict[str, Any]) -> str:
    spec = payload["strategy_definition"]
    lines = [
        f"STRATEGY RESEARCH REPORT — {payload['strategy_name']}",
        f"Ticker: {payload['ticker']}", f"Period: {payload['test_period']}",
        f"Provider: {payload['data_provider']}", f"Generated: {payload['generated_at_utc']}", "",
        "EXECUTION ASSUMPTIONS",
        f"- Timing: {spec.get('execution', 'Next open')}",
        f"- Initial capital: {spec.get('initial_capital', 100000.0):,.2f}",
        f"- Position fraction: {spec.get('position_fraction', 1.0):.1%}",
        f"- Commission: {spec.get('commission_bps', 0.0):.2f} bps",
        f"- Slippage: {spec.get('slippage_bps', 0.0):.2f} bps",
        f"- Stop loss: {spec.get('stop_loss_pct', 0.0):.2f}%",
        f"- Take profit: {spec.get('take_profit_pct', 0.0):.2f}%",
        f"- Trailing stop: {spec.get('trailing_stop_pct', 0.0):.2f}%", "",
        "STRATEGY DEFINITION", json.dumps(spec, indent=2, default=str), "", "PERFORMANCE",
    ]
    for key, value in payload.get("performance", {}).items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)
