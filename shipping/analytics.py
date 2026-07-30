"""Descriptive analytics for live AIS snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from .classification import infer_flow


def enrich_vessels(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["flow"] = [infer_flow(course, speed) for course, speed in zip(result.get("course"), result.get("speed_knots"))]
    result["display_name"] = result["name"].fillna("MMSI " + result["mmsi"].astype(str))
    result["speed_knots"] = pd.to_numeric(result["speed_knots"], errors="coerce")
    result["last_update"] = pd.to_datetime(result["last_update"], utc=True, errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    result["age_minutes"] = (now - result["last_update"]).dt.total_seconds() / 60.0
    return result


def fleet_summary(frame: pd.DataFrame) -> dict[str, float | int | str]:
    if frame.empty:
        return {
            "total": 0,
            "tankers": 0,
            "cargo": 0,
            "passenger": 0,
            "inbound": 0,
            "outbound": 0,
            "average_speed": 0.0,
            "last_update": "N/D",
        }
    moving = frame.loc[frame["speed_knots"].fillna(0) >= 1.0]
    latest = frame["last_update"].max()
    return {
        "total": int(len(frame)),
        "tankers": int(frame["category"].isin(["Tanker", "Gas carrier"]).sum()),
        "cargo": int((frame["category"] == "Cargo").sum()),
        "passenger": int((frame["category"] == "Passenger").sum()),
        "inbound": int((frame["flow"] == "Inbound").sum()),
        "outbound": int((frame["flow"] == "Outbound").sum()),
        "average_speed": float(moving["speed_knots"].mean()) if not moving.empty else 0.0,
        "last_update": latest.strftime("%H:%M:%S UTC") if pd.notna(latest) else "N/D",
    }


def congestion_label(frame: pd.DataFrame) -> str:
    """Descriptive live snapshot, not a calibrated congestion index."""
    if frame.empty:
        return "NO DATA"
    slow_share = float((frame["speed_knots"].fillna(0) < 2.0).mean())
    if len(frame) >= 80 and slow_share >= 0.45:
        return "ELEVATED"
    if len(frame) >= 40 and slow_share >= 0.30:
        return "WATCH"
    return "NORMAL"
