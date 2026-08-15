"""
BOT-BUILD-BUFFER-PCC-076 — Pines de reaccion 👍 + bypass PCC por identidad pendiente.

P1: MessageBuffer.clear_messages limpia solo _buffers, preserva _active_tasks/wamids
P2: Tras T1+T2 textos drenados + 👍, el agregado contiene exactamente "Sí"
P3: run_checker con habeas aceptado + identidad pendiente fuerza bypass_strict=True
P4: Regresion: habeas + identidad completa mantiene rama estricta
P5: Antidrift frontera: clear_messages solo se invoca en la rama no-reaccion
"""

import ast
from pathlib import Path

import pytest

from app.services.message_buffer import MessageBuffer
from app.services.agentic_loop_service import AgenticOrchestrator


PHONE_E164 = "+573192564288"
WAMID_T1 = "wamid.t1"
WAMID_T2 = "wamid.t2"
WAMID_REACTION = "wamid.reaction"


# -----------------------------------------------------------------------------
# P1 / Fix A — clear_messages preserve semantics
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p1_clear_messages_preserves_active_task_and_wamids():
    """
    clear_messages elimina _buffers pero NO toca _active_tasks ni los
    registros de wamid (_processed_wamids / _added_wamids).
    """
    mb = MessageBuffer(debounce_seconds=0.01)

    await mb.add_message(PHONE_E164, "T1", WAMID_T1)
    assert mb._buffers.get(PHONE_E164) == ["T1"]
    assert mb._active_tasks.get(PHONE_E164) == WAMID_T1
    assert WAMID_T1 in mb._processed_wamids[PHONE_E164]
    assert WAMID_T1 in mb._added_wamids[PHONE_E164]

    await mb.clear_messages(PHONE_E164)

    assert PHONE_E164 not in mb._buffers
    assert mb._active_tasks.get(PHONE_E164) == WAMID_T1, "active task no preservada"
    assert WAMID_T1 in mb._processed_wamids[PHONE_E164], "wamid registry alterada"
    assert WAMID_T1 in mb._added_wamids[PHONE_E164], "wamid registry alterada"


# -----------------------------------------------------------------------------
# P2 / Fix A — reaccion pura tras textos drenados
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p2_reaction_aggregates_only_own_body_after_text_drain():
    """
    Secuencia: T1 y T2 son textos ya procesados (drenados por clear_messages);
    la reaccion 👍 agrega su propio cuerpo "Sí". El agregado no debe contener
    los textos anteriores.
    """
    mb = MessageBuffer(debounce_seconds=0.01)

    # Textos individuales: se registran y se drenan inmediatamente (emulando
    # el comportamiento de la frontera post-fix).
    await mb.add_message(PHONE_E164, "Me interesa una moto doble proposito", WAMID_T1)
    await mb.clear_messages(PHONE_E164)
    await mb.add_message(PHONE_E164, "Cual me recomiendas", WAMID_T2)
    await mb.clear_messages(PHONE_E164)

    # Llega la reaccion
    await mb.add_message(PHONE_E164, "Sí", WAMID_REACTION)
    aggregated = await mb.get_aggregated_message(PHONE_E164)

    assert aggregated == "Sí", f"agregado contaminado: {aggregated!r}"
    assert "moto" not in aggregated.lower()


# -----------------------------------------------------------------------------
# P3 / Fix B — bypass PCC por identidad pendiente post-habeas
# -----------------------------------------------------------------------------

def test_p3_run_checker_identity_pending_bypass_is_narrow():
    """
    PHASE_2_HABEAS_DATA post-habeas con identidad pendiente:
    (a) Si la respuesta es una pregunta de recoleccion de identidad,
        se fuerza bypass_strict (la fase prohibe $/imagen).
    (b) Si la respuesta es una oferta con precio/imagen, NO se escapa del PCC
        solo porque falte ciudad/nombre.
    """
    orchestrator = AgenticOrchestrator()
    prospect_data = {
        "phone": PHONE_E164,
        "habeas_data_accepted": True,
        "nombre": None,
        "ciudad": None,
    }

    # (a) pregunta de identidad → bypass
    validation = orchestrator.run_checker(
        bot_response="¿Desde qué ciudad nos escribes?",
        is_catalog_query=True,
        prospect_data=prospect_data,
        user_prompt="quiero una moto doble proposito",
        trace_id="P3a",
    )
    assert validation["success"] is True, validation
    assert validation.get("bypass_strict") is True, validation

    # (b) oferta catalogo → no bypass
    validation = orchestrator.run_checker(
        bot_response="TOP RESULT: TVS Raider 125. Precio: $6.000.000 ![TVS Raider 125](https://img.url/r125.png)",
        is_catalog_query=True,
        prospect_data=prospect_data,
        user_prompt="quiero una moto doble proposito",
        trace_id="P3b",
    )
    assert validation["success"] is False, validation
    assert validation.get("bypass_strict") is not True, validation


# -----------------------------------------------------------------------------
# P4 / Fix B — regresion: identidad completa mantiene estricta
# -----------------------------------------------------------------------------

def test_p4_run_checker_strict_regressions():
    """
    Regresion: bypass solo aplica con habeas aceptado E identidad pendiente.
    (a) identidad completa → rama estricta intacta.
    (b) habeas no aceptado → rama estricta intacta.
    """
    orchestrator = AgenticOrchestrator()

    # (a) identidad completa
    validation = orchestrator.run_checker(
        bot_response="¿Desde qué ciudad nos escribes?",
        is_catalog_query=True,
        prospect_data={
            "phone": PHONE_E164,
            "habeas_data_accepted": True,
            "nombre": "Juan Perez",
            "ciudad": "Bogota",
        },
        user_prompt="quiero una moto doble proposito",
        trace_id="P4a",
    )
    assert validation["success"] is False, validation
    assert validation.get("bypass_strict") is not True, validation

    # (b) habeas no aceptado
    validation = orchestrator.run_checker(
        bot_response="¿Desde qué ciudad nos escribes?",
        is_catalog_query=True,
        prospect_data={
            "phone": PHONE_E164,
            "habeas_data_accepted": False,
            "nombre": None,
            "ciudad": None,
        },
        user_prompt="quiero una moto doble proposito",
        trace_id="P4b",
    )
    assert validation["success"] is False, validation
    assert validation.get("bypass_strict") is not True, validation


# -----------------------------------------------------------------------------
# P5 / Fix A — antidrift frontera whatsapp.py
# -----------------------------------------------------------------------------

def test_p5_frontier_calls_clear_messages_only_for_non_reaction():
    """
    La frontera debe invocar add_message para todo tipo (idempotencia) y
    clear_messages SOLO bajo la guarda msg_type != 'reaction'.
    """
    src_path = Path(__file__).resolve().parents[1] / "app/routers/whatsapp.py"
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Localizar la llamada a add_message en el bloque de idempotencia
    add_message_call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            call = node.value
            func = call.func
            if isinstance(func, ast.Attribute) and func.attr == "add_message":
                add_message_call = node
                break

    assert add_message_call is not None, "no se encontro add_message en la frontera"

    # Recorrer hacia arriba buscando el bloque que contiene add_message y la
    # guarda msg_type != 'reaction' + clear_messages dentro del mismo bloque.
    # Estrategia: encontrar el If cuya rama contiene el Await(clear_messages).
    clear_inside_non_reaction = False
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # La guarda debe ser msg_type != 'reaction'
            guard_src = ast.get_source_segment(src, node.test) or ""
            if "msg_type" in guard_src and "reaction" in guard_src:
                for child in ast.walk(node):
                    if isinstance(child, ast.Await) and isinstance(child.value, ast.Call):
                        child_func = child.value.func
                        if isinstance(child_func, ast.Attribute) and child_func.attr == "clear_messages":
                            clear_inside_non_reaction = True
                            break

    assert clear_inside_non_reaction, (
        "clear_messages no esta protegido por la guarda msg_type != 'reaction'"
    )

    # Confirmar operador != y no solo presencia de las palabras
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and func.attr == "clear_messages":
                parent_if = None
                for ancestor in ast.walk(tree):
                    if isinstance(ancestor, ast.If):
                        if node in ast.walk(ancestor):
                            parent_if = ancestor
                            break
                assert parent_if is not None, "clear_messages fuera de cualquier If"
                test = parent_if.test
                assert isinstance(test, ast.Compare), "guarda no es comparacion"
                assert len(test.ops) == 1 and isinstance(test.ops[0], ast.NotEq), (
                    "clear_messages no esta bajo msg_type != 'reaction'"
                )
                left = ast.get_source_segment(src, test.left) or ""
                comparators = [ast.get_source_segment(src, c) for c in test.comparators]
                assert left.strip() == "msg_type" and any(
                    c is not None and "reaction" in c for c in comparators
                ), "guarda inesperada"
