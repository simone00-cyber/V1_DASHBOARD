import pytest

from shipping.providers.hormuz_strait_monitor import HormuzMonitorError, validate_payload


def sample_payload():
    return {
        "success": True,
        "data": {
            "straitStatus": {},
            "shipCount": {},
            "throughput": {},
            "insurance": {},
            "lastUpdated": "2026-07-24T21:29:29Z",
        },
        "timestamp": "2026-07-24T21:29:29Z",
    }


def test_validate_payload_extracts_data_and_timestamp():
    data, timestamp = validate_payload(sample_payload())
    assert "shipCount" in data
    assert timestamp == "2026-07-24T21:29:29Z"


def test_validate_payload_rejects_missing_required_section():
    payload = sample_payload()
    del payload["data"]["insurance"]
    with pytest.raises(HormuzMonitorError):
        validate_payload(payload)
