from app.rag.qdrant_store import COLLECTION


def test_metadata_filter_shape():
    filt = {"document_type": "vendor_contract", "vendor_id": "VENDOR_AWS", "country": "IN"}
    assert filt["document_type"] == "vendor_contract"
    assert COLLECTION


def test_historical_case_payload():
    payload = {
        "document_type": "historical_case",
        "exception_type": "AMOUNT_MISMATCH",
        "vendor_id": "VENDOR_AWS",
    }
    assert payload["document_type"] == "historical_case"
