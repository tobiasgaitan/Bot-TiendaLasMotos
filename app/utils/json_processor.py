"""
JSON Processor Utility (JSON Voorhees Protocol)
Handles cleanup, normalization, and stabilization of LLM-generated JSON strings.
"""

import json
import re
import logging
import unicodedata
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

def clean_json_voorhees(text: str) -> Tuple[Dict[str, Any], bool]:
    """
    Main entry point for the JSON Voorhees protocol.
    Cleans, normalizes, and parses JSON text from LLM outputs.
    
    Returns:
        tuple: (parsed_dict, is_valid)
    """
    if not text or not isinstance(text, str):
        return _get_fallback_state(), False

    # 1. strip_markdown: Remove ```json and ``` wrappers
    cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', text).strip()
    
    # In case there are multiple blocks or weird content outside blocks, 
    # try to find the first '{' and last '}'
    start_index = cleaned.find('{')
    end_index = cleaned.rfind('}')
    if start_index != -1 and end_index != -1:
        cleaned = cleaned[start_index:end_index + 1]

    try:
        # 2. fix_quotes: Standardize smart quotes and handle internal newlines
        # Replace common smart quotes
        cleaned = cleaned.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
        
        # 3. remove_trailing_commas: Standard JSON doesn't allow trailing commas in objects/arrays
        # This regex removes commas followed by closing braces or brackets, handling optional whitespace
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)

        # 4. normalize_utf8: Ensure consistent encoding for names/cities with accents
        cleaned = unicodedata.normalize('NFC', cleaned)
        
        # 5. sanitize_pii: Basic protection against injection or malformed strings
        # Truncate potentially dangerous long strings or those with suspicious characters
        # Note: This is a safe parse attempt first
        parsed = json.loads(cleaned)
        
        # Post-parse sanitization of critical fields
        sanitized = _sanitize_fields(parsed)
        
        # 6. Final verification: ensure it can be dumped safely as UTF-8
        # This catch-all ensures firestore won't reject it
        json_str = json.dumps(sanitized, ensure_ascii=False)
        return json.loads(json_str), True

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"❌ JSON Voorhees Failure: {str(e)} | Raw: {text[:200]}...")
        return _get_fallback_state(), False

def _sanitize_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitizes PII and trims fields to prevent injection or DB bloat."""
    if not isinstance(data, dict):
        return data
        
    critical_fields = ["nombre", "name", "ciudad", "city", "motoInteres"]
    
    for field in critical_fields:
        if field in data and isinstance(data[field], str):
            val = data[field].strip()
            # 5. sanitize_pii: Basic protection against injection or malformed strings
            # Remove control characters and non-printable
            val = "".join(ch for ch in val if unicodedata.category(ch)[0] != "C")
            # Strict Regex Sanitization: Keep only letters, numbers, spaces, dots and dashes
            # This implements the [^\w\s] requirement plus safe connectors
            val = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.\-]', '', val)
            # Truncate to safe length (50 chars)
            data[field] = val[:50]
            
    return data

def _get_fallback_state() -> Dict[str, Any]:
    """Returns the minimal state preserved during failure as per contract."""
    import datetime
    return {
        "error": True,
        "cleanup_status": "failed",
        "timestamp": datetime.datetime.now().isoformat(),
        "preserved_minimal": True
    }
