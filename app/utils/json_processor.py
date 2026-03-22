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

def clean_json_voorhees(text: str, session_id: str = "unknown", last_intent: str = "unknown") -> Tuple[Dict[str, Any], bool]:
    """
    Main entry point for the JSON Voorhees protocol.
    Cleans, normalizes, and parses JSON text from LLM outputs.
    
    Returns:
        tuple: (parsed_dict, is_valid)
    """
    if not text or not isinstance(text, str):
        return _get_fallback_state(session_id, last_intent), False

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
        
        # 5. Post-parse sanitization and type adaptation
        parsed = json.loads(cleaned)
        
        # Capa de Adaptador: Ensure boolean integrity before sanitization
        adapted = _ensure_boolean_integrity(parsed)
        
        # Post-parse sanitization of critical fields
        sanitized = _sanitize_fields(adapted)
        
        # 6. Final verification: ensure it can be dumped safely as UTF-8
        # This catch-all ensures firestore won't reject it
        json_str = json.dumps(sanitized, ensure_ascii=False)
        return json.loads(json_str), True

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"🚨 [JSON VOORHEES FATAL] Fallo de parseo. Texto crudo recibido: {cleaned}")
        logger.error(f"❌ JSON Voorhees Failure: {str(e)} | Raw snippet: {text[:200]}...")
        return _get_fallback_state(session_id, last_intent), False

def _ensure_boolean_integrity(data: Any) -> Any:
    """
    Capa de Adaptador Estricta: Casts potential boolean strings/emojis to bool primitive.
    Targets 'habeas_data_accepted' specifically as per JSON Voorhees Hardened Protocol.
    """
    if not isinstance(data, dict):
        return data
        
    # Truthy mapping as per mandatory directive
    truthy = {"true", "sí", "si", "ok", "👍", "✅", "👌"}
    
    extracted = data.get("extracted")
    if isinstance(extracted, dict):
        val = extracted.get("habeas_data_accepted")
        if val is not None:
            if isinstance(val, bool):
                pass # Already a primitive bool
            elif isinstance(val, str):
                val_clean = val.lower().strip()
                extracted["habeas_data_accepted"] = val_clean in truthy
            else:
                # Any other type (numbers, None, etc.) defaults to False as per directive
                extracted["habeas_data_accepted"] = False
                
    return data

def _sanitize_fields(data: Any) -> Any:
    """Sanitizes PII and trims fields recursively to handle nested structures."""
    if isinstance(data, list):
        return [_sanitize_fields(item) for item in data]
        
    if not isinstance(data, dict):
        return data
        
    # Restoration of 'moto_interest' as per nativa extraction schema
    critical_fields = ["nombre", "name", "ciudad", "city", "moto_interest", "fullName", "location"]
    
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            data[key] = _sanitize_fields(value)
        elif key in critical_fields and isinstance(value, str):
            # Remove control characters
            val = "".join(ch for ch in value if unicodedata.category(ch)[0] != "C")
            # Strict Regex Sanitization: keep alphanumeric, spaces, dots, dashes and accents
            val = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.\-]', '', val)
            # Truncate to safe length (50 chars) and trim residual spaces from emoji removal
            data[key] = val.strip()[:50]
            
    return data

def _get_fallback_state(session_id: str = "unknown", last_valid_intent: str = "unknown") -> Dict[str, Any]:
    """Returns the minimal state preserved during failure as per contract."""
    import datetime
    return {
        "session_id": session_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "last_valid_intent": last_valid_intent,
        "cleanup_status": "failed",
        "error": True,
        "preserved_minimal": True
    }
