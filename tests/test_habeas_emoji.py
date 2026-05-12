import pytest
from app.utils.json_processor import clean_json_voorhees

def test_habeas_data_accepted_emoji_extraction():
    """Validates that emojis in habeas_data_accepted are correctly casted to boolean."""
    raw_json = '{"summary": "Test", "extracted": {"habeas_data_accepted": "👍", "name": "Juan 👍"}}'
    parsed, is_valid = clean_json_voorhees(raw_json)
    
    assert is_valid is True
    # The adapter should have casted the emoji to True
    assert parsed["extracted"]["habeas_data_accepted"] is True
    # The name should have been sanitized (emoji removed) as per security history
    assert parsed["extracted"]["name"] == "Juan"

def test_habeas_data_accepted_various_truthy():
    """Validates all supported truthy strings and emojis."""
    truthy_cases = ["true", "Sí", "si", "ok", "✅", "👌"]
    for case in truthy_cases:
        raw = f'{{"summary": "Test", "extracted": {{"habeas_data_accepted": "{case}"}}}}'
        parsed, _ = clean_json_voorhees(raw)
        assert parsed["extracted"]["habeas_data_accepted"] is True, f"Failed for case: {case}"

def test_habeas_data_accepted_falsy_and_edge_cases():
    """Validates that non-truthy values default to False as per directive."""
    falsy_cases = ["false", "no", "tal vez", "n/a", "unknown"]
    for case in falsy_cases:
        raw = f'{{"summary": "Test", "extracted": {{"habeas_data_accepted": "{case}"}}}}'
        parsed, _ = clean_json_voorhees(raw)
        assert parsed["extracted"]["habeas_data_accepted"] is False, f"Failed for case: {case}"

def test_moto_interest_key_sanitization():
    """Validates that moto_interest is correctly recognized for PII sanitization."""
    raw_json = '{"summary": "Test", "extracted": {"moto_interest": "TVS Apache 160!!!", "habeas_data_accepted": true}}'
    parsed, _ = clean_json_voorhees(raw_json)
    
    # Should strip the !!! as non-alphanumeric
    assert parsed["extracted"]["moto_interest"] == "TVS Apache 160"
