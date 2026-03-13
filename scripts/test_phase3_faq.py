#!/usr/bin/env python3
"""
LOCAL QA TEST — Phase 3 FAQ Behavior
=====================================
Proves that the LLM:
  BEFORE fix: ignores 'Con crédito, ¿qué necesito?' and outputs ONLY the survey question
  AFTER fix:  answers the FAQ first, THEN appends the friendly survey transition

Requirements:
  - GOOGLE_APPLICATION_CREDENTIALS must be set OR you have `gcloud auth application-default login`
  - pip install google-cloud-aiplatform google-cloud-firestore python-dotenv

Usage:
  python3 scripts/test_phase3_faq.py
"""

import os
import sys
import time

# ── Environment bootstrap ───────────────────────────────────────────────────
# Load .env if present (for local dev; Cloud Run uses env vars directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "tiendalasmotos")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# ── Vertex AI + Firestore imports ───────────────────────────────────────────
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Tool, FunctionDeclaration, GenerationConfig

try:
    from google.cloud import firestore as fs
    db = fs.Client(project=GCP_PROJECT)
    print(f"✅ Firestore connected: {GCP_PROJECT}")
except Exception as e:
    print(f"⚠️  Firestore unavailable ({e}). Using FALLBACK_PROMPT from local prompts.py")
    db = None

# ── Load system instruction (mirrors production logic) ─────────────────────
SYSTEM_INSTRUCTION = None

if db:
    try:
        doc = db.collection("configuracion").document("juan_pablo_personality").get()
        if doc.exists and doc.to_dict().get("system_instruction"):
            SYSTEM_INSTRUCTION = doc.to_dict()["system_instruction"]
            print("✅ System instruction loaded from Firestore (PRODUCTION PROMPT)")
    except Exception as e:
        print(f"⚠️  Firestore read failed ({e})")

if not SYSTEM_INSTRUCTION:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
    SYSTEM_INSTRUCTION = JUAN_PABLO_SYSTEM_INSTRUCTION
    print("✅ System instruction loaded from local prompts.py (FALLBACK)")

# ── Initialize Vertex AI ────────────────────────────────────────────────────
vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)
model = GenerativeModel(
    "gemini-2.5-flash-preview-04-17",
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config=GenerationConfig(
        temperature=0.4,
        max_output_tokens=1024,
    )
)

# ── Mock prospect data (mirrors a real Phase 3 session) ─────────────────────
MOCK_PROSPECT = {
    "exists": True,
    "name": "Tobias",
    "ciudad": "Orihueca",
    "moto_interest": "MRX 150",
    "payment_method": "crédito",   # Phase 1 + 2 complete
    "summary": "Usuario interesado en MRX 150 a crédito. Aceptó política de datos.",
}

# ── Build the exact same prompt that ai_brain.py builds ─────────────────────
def build_prompt(user_message: str, prospect: dict, skip_greeting: bool = True) -> str:
    prompt = f"{SYSTEM_INSTRUCTION}\n\n"
    prompt += "Your name is Juan Pablo. NEVER address the user as Juan Pablo.\n"

    if prospect.get("exists"):
        name = prospect.get("name", "")
        prompt += "═" * 67 + "\n"
        prompt += "INFORMACIÓN DEL PROSPECTO (CRM):\n"
        if name:
            prompt += f"- Nombre: {name}\n"
        if prospect.get("ciudad"):
            prompt += f"- Ciudad: {prospect['ciudad']}\n"
        if prospect.get("moto_interest"):
            prompt += f"- Interés en moto: {prospect['moto_interest']}\n"
        if prospect.get("payment_method"):
            prompt += f"- Forma de pago: {prospect['payment_method']}\n"
        if prospect.get("summary"):
            prompt += f"- Resumen previo: {prospect['summary']}\n"
        prompt += f"\n⚠️ INSTRUCCIÓN DE IDENTIDAD: El nombre del usuario es {name}.\n"
        prompt += "PROHIBIDO usar formalismos como 'Señor' o 'Señora'.\n"
        prompt += "PROHIBIDO repetir el nombre del usuario de forma constante.\n"
        prompt += "Comunícate de manera natural, humana, directa y empática.\n"
        prompt += "═" * 67 + "\n\n"

    # Mock chat history (Phase 2 acceptance happened one turn ago)
    history_lines = [
        "Juan Pablo: ¡Qué buena decisión! Para poder continuar con tu solicitud de crédito, necesito pedirte un permiso. ¿Me autorizas el tratamiento de tus datos personales para el estudio de crédito? Consulta nuestra política aquí: https://tiendalasmotos.com/politica-de-privacidad",
        "Usuario: Sí, acepto la política de datos.",
    ]
    if history_lines:
        prompt += "📜 HISTORIAL RECIENTE (Últimos mensajes):\n"
        for h in history_lines:
            prompt += f"- {h}\n"
        prompt += "═" * 67 + "\n\n"

    if skip_greeting:
        prompt += "\n[SYSTEM: STRICT RULE: DO NOT start your response with 'Hola' or any greeting. Jump straight into your answer.]\n"

    # Anti-hallucination guardrail
    prompt += "═" * 67 + "\n"
    prompt += "🔒 CRITICAL RULE (ANTI-HALLUCINATION):\n"
    prompt += "- NEVER hallucinate prices or specs. Only use catalog tool data.\n"
    prompt += "═" * 67 + "\n\n"

    return prompt


def run_test(label: str, user_message: str):
    """Run a single test case and print results."""
    print(f"\n{'='*70}")
    print(f"TEST: {label}")
    print(f"USER: {user_message}")
    print(f"{'='*70}")

    # Mirror the Moto Anchor enrichment from whatsapp.py
    enriched = user_message
    moto = MOCK_PROSPECT.get("moto_interest")
    if moto and len(user_message) < 60:
        enriched = f"[Contexto CRM: Hablando sobre {moto}]\nMensaje: {user_message}"
        print(f"ENRICHED: {enriched}")

    prompt = build_prompt(enriched, MOCK_PROSPECT)
    
    start = time.time()
    chat = model.start_chat()
    response = chat.send_message(prompt + f"\n\nUsuario: {enriched}")
    elapsed = time.time() - start

    reply = response.text.strip() if response.text else "[NO TEXT RESPONSE]"
    char_count = len(reply)

    print(f"\nBOT RESPONSE ({char_count} chars, {elapsed:.1f}s):")
    print(f"  ┌─────────────────────────────────────────────────────")
    for line in reply.split("\n"):
        print(f"  │ {line}")
    print(f"  └─────────────────────────────────────────────────────")

    # ── Assertions ─────────────────────────────────────────────────────────
    failures = []

    # 1. Response must be longer than just a survey question (28 chars = FAIL)
    if char_count < 60:
        failures.append(f"❌ Response too short ({char_count} chars). LLM is likely skipping the FAQ answer.")
    else:
        print(f"  ✅ Length OK ({char_count} chars > 60)")

    # 2. Must NOT start directly with a survey question without answering first
    starts_with_survey = any(reply.strip().startswith(q) for q in [
        "¿En qué trabaja", "¿en qué trabaja",
        "Para empezar", "para empezar",
        "¡Perfecto! Para empezar",
    ])
    if starts_with_survey:
        failures.append("❌ Response starts directly with survey question (FAQ was ignored).")
    else:
        print("  ✅ Response does NOT start with a raw survey question")

    # 3. Must contain SOME answer to the credit FAQ
    credit_faq_keywords = ["necesitas", "necesitarás", "requieres", "cédula", "ingresos",
                           "documentos", "requiere", "proceso", "cuotas", "requisito"]
    has_faq_answer = any(k in reply.lower() for k in credit_faq_keywords)
    if not has_faq_answer:
        failures.append("❌ Response does not appear to answer the credit FAQ ('¿qué necesito?')")
    else:
        print("  ✅ Response contains credit FAQ answer keywords")

    # 4. Must contain the friendly Phase 3 transition
    transition_keywords = ["empecemos", "preguntas", "pocas", "sencillas", "trabajas", "en qué trabaja"]
    has_transition = any(k in reply.lower() for k in transition_keywords)
    if not has_transition:
        failures.append("❌ Response does not include Phase 3 survey transition")
    else:
        print("  ✅ Response contains Phase 3 transition")

    if failures:
        print(f"\n  ⚠️  ASSERTION FAILURES:")
        for f in failures:
            print(f"    {f}")
        return False
    else:
        print(f"\n  🎉 ALL ASSERTIONS PASSED")
        return True


# ── Main test runner ────────────────────────────────────────────────────────
if __name__ == "__main__":
    results = []

    # Test Case 1: The exact failing message from production logs
    results.append(run_test(
        label="EXACT PRODUCTION FAILURE — organic FAQ after Phase 2 acceptance",
        user_message="Con crédito, ¿qué necesito?"
    ))

    # Test Case 2: A different organic question (regression guard)
    results.append(run_test(
        label="REGRESSION — 'cuánto tiempo tarda el crédito?'",
        user_message="¿Cuánto tiempo tarda el estudio de crédito?"
    ))

    # Test Case 3: Verify that eventually the survey transition appears
    results.append(run_test(
        label="CONTROL — user gives no question (pure Phase 3 start)",
        user_message="Listo, proceda."
    ))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*70}")
    print(f"RESULTS: {passed}/{total} tests passed")
    if passed == total:
        print("✅ ALL TESTS PASSED — safe to deploy")
    else:
        print("❌ TESTS FAILED — do NOT deploy. Fix required.")
    sys.exit(0 if passed == total else 1)
