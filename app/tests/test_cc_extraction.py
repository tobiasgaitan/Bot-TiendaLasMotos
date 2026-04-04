import re
import logging

# Define logic directly to certify Before applying to CatalogService
def _extract_cc_logic(data):
    """
    Simulación de DisplacementExtractorV2
    Regex: r'\d+(?:\.\d+)?'
    Flow: Match -> float() -> int() (Truncate)
    """
    # 1. Check root fields (case-insensitive)
    def find_in_dict(d, keys):
        if not isinstance(d, dict): return None
        d_lower = {str(k).lower(): v for k, v in d.items()}
        for k in keys:
            if k in d_lower: return d_lower[k]
        return None

    # Priority 1: root
    cc_val = find_in_dict(data, ["displacement", "cilindraje", "cc"])
    
    # Priority 2: fichatecnica
    if cc_val is None:
        ft = data.get("fichatecnica") or data.get("ficha_tecnica") or {}
        cc_val = find_in_dict(ft, ["cilindraje", "displacement", "cc", "rango cilindraje"])

    if cc_val is None:
        return 0

    try:
        # Regex strict for numeric component (v6.9.0)
        match = re.search(r'\d+(?:\.\d+)?', str(cc_val))
        if match:
            # Casteo float -> Truncate int (Legal Requirement)
            return int(float(match.group(0)))
        return 0
    except (ValueError, TypeError):
        return 0

# --- Test Suite ---
test_cases = [
    {"name": "Apache 160 (String CC)", "data": {"fichatecnica": {"CILINDRAJE": "159.7 CC"}}, "expected": 159},
    {"name": "Apache 160 (String Float)", "data": {"fichatecnica": {"cilindraje": "159.7"}}, "expected": 159},
    {"name": "Apache 160 (Root Double)", "data": {"displacement": 159.7}, "expected": 159},
    {"name": "Pulsar 200 (Clean Int)", "data": {"cc": 199}, "expected": 199},
    {"name": "Empty data", "data": {}, "expected": 0},
    {"name": "Bad String", "data": {"cc": "N/A"}, "expected": 0}
]

def run_tests():
    print("🚀 [CERTIFICATION] Running CC Extraction v2 Tests...")
    all_passed = True
    for t in test_cases:
        result = _extract_cc_logic(t["data"])
        if result == t["expected"]:
            print(f"✅ {t['name']}: {result}cc (Passed)")
        else:
            print(f"❌ {t['name']}: Expected {t['expected']}, got {result} (FAILED)")
            all_passed = False
    
    if all_passed:
        print("\n🏆 [GO] Local Certification Successful.")
    else:
        print("\n🛑 [STOP] Tests Failed. Re-evaluate logic.")
    return all_passed

if __name__ == "__main__":
    run_tests()
