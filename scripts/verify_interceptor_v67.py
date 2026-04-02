import difflib
import sys
import os

# Simular contexto de negocio de ai_brain.py
def calculate_ratio(query, current_interest):
    if not current_interest:
        return 0.0
    return difflib.SequenceMatcher(None, query.lower().strip(), current_interest.lower().strip()).ratio()

def evaluate_interceptor(query, current_interest, exact_threshold=0.95, drift_threshold=0.35):
    ratio = calculate_ratio(query, current_interest)
    # LÓGICA JSON VOORHEES v6.7 (Revisión A)
    if drift_threshold <= ratio < exact_threshold:
        return "BLOCK", ratio
    else:
        return "ALLOW", ratio

def run_tests():
    test_cases = [
        {"name": "Caso A: Búsqueda Idéntica (Apache 160)", "query": "apache 160", "interest": "apache 160", "expected": "ALLOW"},
        {"name": "Caso B: Cambio Radical (Pulsar)", "query": "pulsar", "interest": "apache 160", "expected": "ALLOW"},
        {"name": "Caso C: Drift Peligroso (Apache 160 rtr)", "query": "apache 160 rtr", "interest": "apache 160", "expected": "BLOCK"},
        {"name": "Caso D: Drift Leve (Apach 160)", "query": "apach 160", "interest": "apache 160", "expected": "BLOCK"},
    ]
    
    print("\n--- INICIO DE VALIDACIÓN INTERCEPTOR v6.7 ---\n")
    all_passed = True
    for case in test_cases:
        result, ratio = evaluate_interceptor(case["query"], case["interest"])
        status = "PASSED ✅" if result == case["expected"] else "FAILED ❌"
        if result != case["expected"]:
            all_passed = False
        print(f"{status} | {case['name']:<40} | Ratio: {ratio:.4f} | Result: {result}")
    
    if all_passed:
        print("\nRESULTADO FINAL: EXITOSO. La lógica v6.7 protege el drift y permite coincidencias exactas.")
        sys.exit(0)
    else:
        print("\nRESULTADO FINAL: FALLIDO. Revisar lógica de umbrales.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
