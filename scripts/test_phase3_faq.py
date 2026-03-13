#!/usr/bin/env python3
"""
LOCAL QA TEST — Phase 3 FAQ Behavior
=====================================
Proves the LLM answers 'Con crédito, ¿qué necesito?' BEFORE the survey.

CREDENTIALS (choose one):
  Option A — Gemini API Key (easiest, works locally and in Cloud Shell):
      export GEMINI_API_KEY="your-key-here"   # from https://aistudio.google.com/apikey
      pip3 install google-genai
      python3 scripts/test_phase3_faq.py

  Option B — Cloud Shell ADC (no extra setup needed in Cloud Shell):
      pip3 install google-genai  # then run the same command, no key needed
      python3 scripts/test_phase3_faq.py      # uses GOOGLE_CLOUD_PROJECT env var

WHAT IS TESTED:
  Given: Phase 1+2 complete (name/city/moto/payment=crédito, data policy accepted)
  When:  User sends "Con crédito, ¿qué necesito?"
  Then:  Bot must answer the FAQ (>60 chars) AND include Phase 3 transition.
         FAIL if bot outputs only "¿En qué trabaja actualmente?" (28 chars = P0 bug).
"""

import os
import sys
import time
import warnings
warnings.filterwarnings("ignore")

# ── .env support ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── SDK selection: google-genai preferred, vertexai fallback ─────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", "tiendalasmotos"))
USE_VERTEX = False
client = None

if GEMINI_API_KEY:
    try:
        from google import genai
        from google.genai import types
        client_obj = genai.Client(api_key=GEMINI_API_KEY)
        print(f"✅ Auth: Gemini API Key")
    except ImportError:
        print("❌ google-genai not installed. Run: pip3 install google-genai")
        sys.exit(1)
else:
    # Fall back to vertexai with Application Default Credentials (Cloud Shell)
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        from google import genai
        from google.genai import types
        vertexai.init(project=GCP_PROJECT, location="us-central1")
        USE_VERTEX = True
        client_obj = None
        print(f"✅ Auth: Vertex AI ADC (project={GCP_PROJECT})")
    except Exception as e:
        print(f"❌ No credentials found. Set GEMINI_API_KEY or run in Cloud Shell.")
        print(f"   Detail: {e}")
        sys.exit(1)

# ── Load prompt from app/core/prompts.py ─────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION as SYSTEM_PROMPT
    print(f"✅ Prompt: app/core/prompts.py ({len(SYSTEM_PROMPT)} chars)")
except ImportError as e:
    print(f"❌ Cannot import app/core/prompts.py: {e}")
    sys.exit(1)

# ── Model: MUST match ai_brain.py line 59 exactly ────────────────────────────
MODEL = "gemini-2.5-flash"
print(f"✅ Model: {MODEL}\n")

# ── Mock Prospect (Phase 1 + Phase 2 complete) ────────────────────────────────
PROSPECT = {
    "exists": True, "name": "Tobias", "ciudad": "Orihueca",
    "moto_interest": "MRX 150", "payment_method": "crédito",
    "summary": "Usuario interesado en MRX 150 a crédito. Aceptó política de datos.",
}


def build_prompt(raw_msg: str, p: dict):
    """Mirrors ai_brain.py _generate_with_retry() prompt assembly."""
    ctx = "Your name is Juan Pablo. NEVER address the user as Juan Pablo.\n"
    ctx += "═" * 67 + "\nINFORMACIÓN DEL PROSPECTO (CRM):\n"
    if p.get("name"):      ctx += f"- Nombre: {p['name']}\n"
    if p.get("ciudad"):    ctx += f"- Ciudad: {p['ciudad']}\n"
    if p.get("moto_interest"): ctx += f"- Interés en moto: {p['moto_interest']}\n"
    if p.get("payment_method"): ctx += f"- Forma de pago: {p['payment_method']}\n"
    if p.get("summary"):   ctx += f"- Resumen previo: {p['summary']}\n"
    ctx += (f"\n⚠️ El nombre del usuario es {p['name']}. "
            f"PROHIBIDO usar 'Señor/Señora'. Comunícate de forma natural.\n")
    ctx += "═" * 67 + "\n\n"
    # Phase 2 history
    ctx += ("📜 HISTORIAL RECIENTE:\n"
            "- Juan Pablo: ¿Me autorizas el tratamiento de tus datos? "
            "Política: https://tiendalasmotos.com/politica-de-privacidad\n"
            "- Usuario: Sí, acepto la política de datos.\n"
            "═" * 67 + "\n\n"
            "[SYSTEM: DO NOT start with 'Hola'. Jump into your answer.]\n"
            "🔒 REGLA ANTI-HALLUCINATION: NUNCA inventes precios.\n"
            "═" * 67 + "\n\n")
    # Moto Anchor enrichment (whatsapp.py)
    enriched = raw_msg
    if p.get("moto_interest") and len(raw_msg) < 60:
        enriched = f"[Contexto CRM: Hablando sobre {p['moto_interest']}]\nMensaje: {raw_msg}"
    return ctx + f"Usuario: {enriched}"


def call_model(full_prompt: str) -> str:
    """Call Gemini via google-genai SDK or Vertex AI SDK depending on auth."""
    if USE_VERTEX:
        model = GenerativeModel(
            MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config=GenerationConfig(temperature=0.4, max_output_tokens=1024),
        )
        chat = model.start_chat()
        resp = chat.send_message(full_prompt)
        return resp.text.strip() if resp.text else ""
    else:
        resp = client_obj.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=1024,
            ),
        )
        return resp.text.strip() if resp.text else ""


def run_test(label: str, raw_msg: str,
             expect_faq: bool = True,
             expect_transition: bool = True) -> bool:
    print(f"\n{'='*70}\nTEST: {label}\nUSER: {raw_msg}\n{'='*70}")

    full_prompt = build_prompt(raw_msg, PROSPECT)
    t0 = time.time()
    reply = call_model(full_prompt)
    elapsed = time.time() - t0
    chars = len(reply)

    print(f"\nBOT ({chars} chars, {elapsed:.1f}s):")
    print("  ┌" + "─" * 60)
    for line in reply.split("\n"):
        print(f"  │ {line}")
    print("  └" + "─" * 60)

    fails = []

    if expect_faq:
        if chars < 60:
            fails.append(f"❌ Only {chars} chars — LLM collapsed to survey-only (P0 bug)")
        else:
            print(f"  ✅ Length: {chars} chars (≥60)")

        bad_starts = ["¿En qué trabaja", "¿en qué trabaja",
                      "Para empezar,", "Empecemos con las preguntas"]
        if any(reply.strip().startswith(s) for s in bad_starts):
            fails.append("❌ Opened with bare survey question — FAQ skipped")
        else:
            print("  ✅ Does NOT start with bare survey question")

        faq_kw = ["necesitas", "cédula", "ingresos", "documentos",
                  "requisito", "proceso", "trabajo", "certificado",
                  "referencia", "historial", "cuotas", "plazo"]
        if not any(k in reply.lower() for k in faq_kw):
            fails.append("❌ No credit FAQ content found")
        else:
            print("  ✅ Credit FAQ content present")

    if expect_transition:
        tran_kw = ["preguntas", "pocas", "sencillas", "trabajas", "trabaja",
                   "empecemos", "cuánto llevas"]
        if not any(k in reply.lower() for k in tran_kw):
            fails.append("❌ Missing Phase 3 survey transition")
        else:
            print("  ✅ Phase 3 transition present")

    if fails:
        print("\n  ⚠️  FAILURES:")
        for f in fails:
            print(f"    {f}")
        return False
    print("\n  🎉 ALL ASSERTIONS PASSED")
    return True


if __name__ == "__main__":
    print("🧪  Phase 3 FAQ QA Test Suite")
    res = []
    res.append(run_test("[P0] PRODUCTION FAILURE — FAQ skipped after Phase 2",
                        "Con crédito, ¿qué necesito?"))
    res.append(run_test("[REGRESSION] Different credit FAQ",
                        "¿Cuánto tiempo tarda el estudio de crédito?"))
    res.append(run_test("[CONTROL] No question — direct Phase 3 start",
                        "Listo, proceda.", expect_faq=False, expect_transition=True))
    p, t = sum(res), len(res)
    print(f"\n{'='*70}\nRESULT: {p}/{t} passed — "
          f"{'✅ SAFE TO DEPLOY' if p == t else '❌ DO NOT DEPLOY'}\n{'='*70}")
    sys.exit(0 if p == t else 1)
