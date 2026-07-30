"""AIS vessel classification helpers.

AIS ship type codes identify broad vessel classes. They do not reliably expose
exact cargo, ownership or commercial employment.
"""
from __future__ import annotations

import math
from typing import Any


NAV_STATUS = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Fishing",
    8: "Under way sailing",
    14: "AIS-SART / active",
    15: "Not defined",
}


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("@", "").strip()
    return text or None


def classify_ship_type(code: int | None, name: str | None = None) -> str:
    text = (name or "").upper()
    if "LNG" in text or "LPG" in text:
        return "Gas carrier"
    if code is None:
        return "Other"
    if 20 <= code <= 29:
        return "Wing in ground"
    if code == 30:
        return "Fishing"
    if code in {31, 32}:
        return "Tug / tow"
    if code == 33:
        return "Dredger"
    if code == 34:
        return "Diving"
    if code == 35:
        return "Military"
    if code == 36:
        return "Sailing"
    if code == 37:
        return "Pleasure craft"
    if 40 <= code <= 49:
        return "High speed craft"
    if 50 <= code <= 59:
        return "Service vessel"
    if 60 <= code <= 69:
        return "Passenger"
    if 70 <= code <= 79:
        return "Cargo"
    if 80 <= code <= 89:
        return "Tanker"
    if 90 <= code <= 99:
        return "Other"
    return "Other"


def navigational_status(value: Any) -> str | None:
    code = safe_int(value)
    return NAV_STATUS.get(code, str(code) if code is not None else None)


def infer_flow(course: float | None, speed: float | None) -> str:
    """Indicative Hormuz direction from course over ground.

    Eastbound traffic is labelled outbound from the Gulf; westbound traffic is
    labelled inbound. Slow/stationary or ambiguous courses remain undetermined.
    """
    if course is None or (speed is not None and speed < 1.0):
        return "Undetermined"
    course = course % 360
    if 45 <= course <= 145:
        return "Outbound"
    if 215 <= course <= 325:
        return "Inbound"
    return "Undetermined"
