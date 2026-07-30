from shipping.providers.hormuztracker import HormuzTrackerError, validate_payload


def test_validate_payload_accepts_expected_shape():
    payload = {"meta": {"source": "HormuzTracker"}, "crisis": {"severityScore": 7}}
    assert validate_payload(payload) is payload


def test_validate_payload_rejects_missing_crisis():
    try:
        validate_payload({"meta": {}})
    except HormuzTrackerError:
        pass
    else:
        raise AssertionError("Expected HormuzTrackerError")
