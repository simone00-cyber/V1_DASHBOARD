from datetime import datetime, timezone

from shipping.analytics import enrich_vessels, fleet_summary
from shipping.classification import classify_ship_type, infer_flow
from shipping.chokepoints import CHOKEPOINTS
from shipping.store import VesselStore


def test_hormuz_bounding_box_is_valid():
    box = CHOKEPOINTS["Strait of Hormuz"].ais_bounding_box
    assert len(box) == 2
    assert box[0][0] < box[1][0]
    assert box[0][1] < box[1][1]


def test_ship_type_classification():
    assert classify_ship_type(80) == "Tanker"
    assert classify_ship_type(70) == "Cargo"
    assert classify_ship_type(60) == "Passenger"
    assert classify_ship_type(80, "LNG TEST") == "Gas carrier"


def test_flow_classification_is_explicitly_indicative():
    assert infer_flow(90, 12) == "Outbound"
    assert infer_flow(270, 12) == "Inbound"
    assert infer_flow(180, 12) == "Undetermined"
    assert infer_flow(90, 0.2) == "Undetermined"


def test_store_and_summary():
    store = VesselStore(stale_minutes=45)
    store.upsert(
        "123456789",
        latitude=26.2,
        longitude=56.5,
        name="TEST TANKER",
        category="Tanker",
        speed_knots=10.0,
        course=90.0,
        last_update=datetime.now(timezone.utc),
    )
    frame = enrich_vessels(store.dataframe())
    summary = fleet_summary(frame)
    assert summary["total"] == 1
    assert summary["tankers"] == 1
    assert summary["outbound"] == 1


def test_aisstream_message_normalization():
    from shipping.providers.aisstream import AISStreamCollector

    store = VesselStore(stale_minutes=45)
    collector = AISStreamCollector("test-key", CHOKEPOINTS["Strait of Hormuz"], store)
    collector._handle_message(
        {
            "MessageType": "PositionReport",
            "MetaData": {"ShipName": "TEST VESSEL", "MMSI": 123456789},
            "Message": {
                "PositionReport": {
                    "UserID": 123456789,
                    "Latitude": 26.3,
                    "Longitude": 56.7,
                    "Sog": 12.4,
                    "Cog": 91.0,
                    "TrueHeading": 90,
                    "NavigationalStatus": 0,
                }
            },
        }
    )
    collector._handle_message(
        {
            "MessageType": "ShipStaticData",
            "MetaData": {"ShipName": "TEST VESSEL", "MMSI": 123456789},
            "Message": {
                "ShipStaticData": {
                    "UserID": 123456789,
                    "Name": "TEST VESSEL",
                    "Type": 80,
                    "Destination": "FUJAIRAH",
                    "ImoNumber": 9876543,
                    "MaximumStaticDraught": 12.1,
                    "Dimension": {"A": 200, "B": 50, "C": 20, "D": 20},
                }
            },
        }
    )
    vessel = store.get("123456789")
    assert vessel is not None
    assert vessel.latitude == 26.3
    assert vessel.category == "Tanker"
    assert vessel.destination == "FUJAIRAH"
    assert vessel.length_m == 250
    diagnostics = store.diagnostics()
    assert diagnostics["raw_message_count"] == 2
    assert diagnostics["message_count"] == 2
    assert diagnostics["unhandled_message_count"] == 0
