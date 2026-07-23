"""
Escaneo estático anti fire-and-forget — Etapa 3 Wave 05-02 [BOT-BUILD-ETAPA3-WAVE02-HYGIENE-001]

Certifica de forma ejecutable el hallazgo de la arqueología Etapa 3: el eje
transaccional del embudo comercial (`app/routers/whatsapp.py`) contiene CERO
operaciones fire-and-forget. El test blinda el invariante contra reintroducciones
durante la fragmentación RF-5 (waves 05-03 a 05-05): todo futuro `create_task`
en el router hará FALLAR este test de inmediato.

Metodología (semántica AST — distingue el patrón prohibido del sancionado):
  1. Cero accesos `asyncio.create_task` (llamada o referencia) y cero imports
     `from asyncio import create_task` — las únicas formas reales de fire-and-forget.
  2. Cero llamada DIRECTA `*.create_task(...)` sobre cualquier receptor — fuerza a
     que el encolado GCP Cloud Tasks use la forma sancionada por referencia
     `asyncio.to_thread(client.create_task, ...)` (BOT-BRAIN-ALIGNMENT-099), que es
     awaited y jamás fire-and-forget.
  3. Léxico: cero ocurrencias del token 'fire_and_forget' tras despojar comentarios
     y literales string (tokenize).

Excepción sancionada (NO violación): `client.create_task` de `tasks_v2.CloudTasksClient`
(API GCP Cloud Tasks) pasado POR REFERENCIA a `asyncio.to_thread` en
`_enqueue_cloud_task` (L337-382) — encolado awaited, fuera del patrón asyncio.create_task.

Contexto sancionado adicional: `background_tasks.add_task` solo en los 3 puntos de
delegación certificados (statuses ×2, ingesta del mensaje ×1) — pineado en el
tercer test para detectar nuevas delegaciones no aprobadas.
"""
import ast
import io
import tokenize
from pathlib import Path

WHATSAPP_PY = Path(__file__).resolve().parent.parent / "app" / "routers" / "whatsapp.py"

# Delegaciones BackgroundTasks sancionadas (fuera del eje de escritura de estado):
# statuses (acuses de entrega, auditoría) e ingesta del mensaje (frontera 200-OK a Meta).
SANCTIONED_ADD_TASK_TARGETS = {"_handle_statuses_background", "_handle_message_background"}


def _strip_comments_and_strings(source: str) -> str:
    """Devuelve el código conservando solo tokens de estructura (NAME/OP/NUMBER…).

    WHY: tokenize garantiza que el despojo de comentarios/strings respeta la
    gramática real de Python (nada de regex frágiles sobre triple-comillas).
    """
    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.INDENT, tokenize.DEDENT, tokenize.NL):
            continue
        kept.append(tok.string)
    return " ".join(kept)


def test_whatsapp_router_has_zero_asyncio_create_task_usage():
    """
    AST scan: cero accesos `asyncio.create_task` (como llamada O como referencia),
    cero nombres desnudos `create_task` y cero `from asyncio import create_task`.
    """
    tree = ast.parse(WHATSAPP_PY.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        # asyncio.create_task en cualquier forma (llamada o referencia).
        if isinstance(node, ast.Attribute) and node.attr == "create_task" \
                and isinstance(node.value, ast.Name) and node.value.id == "asyncio":
            violations.append(("asyncio.create_task", node.lineno))
        # Nombre desnudo create_task (alias importado).
        elif isinstance(node, ast.Name) and node.id == "create_task":
            violations.append(("create_task (nombre desnudo)", node.lineno))
        # from asyncio import create_task
        elif isinstance(node, ast.ImportFrom) and node.module == "asyncio":
            for alias in node.names:
                if alias.name == "create_task":
                    violations.append(("from asyncio import create_task", node.lineno))
    assert violations == [], (
        f"VIOLACIÓN fire-and-forget: uso de asyncio.create_task en whatsapp.py "
        f"{violations}. El eje transaccional exige await bloqueante."
    )


def test_whatsapp_router_has_zero_direct_create_task_calls():
    """
    AST scan: cero LLAMADA directa `*.create_task(...)` sobre cualquier receptor.
    La forma sancionada de encolado GCP pasa el método POR REFERENCIA a
    `asyncio.to_thread(client.create_task, ...)` — nunca como llamada directa.
    """
    tree = ast.parse(WHATSAPP_PY.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "create_task":
            violations.append(node.lineno)
    assert violations == [], (
        f"VIOLACIÓN fire-and-forget: llamada(s) directa(s) create_task en whatsapp.py "
        f"líneas {violations}. El encolado GCP sancionado usa la referencia "
        f"asyncio.to_thread(client.create_task, ...)."
    )


def test_whatsapp_router_has_zero_fire_and_forget_token_in_code():
    """
    Escaneo léxico: tras despojar comentarios y strings, el token
    'fire_and_forget' no existe en el código del router.
    """
    sanitized = _strip_comments_and_strings(WHATSAPP_PY.read_text(encoding="utf-8"))
    assert "fire_and_forget" not in sanitized, (
        "VIOLACIÓN: token 'fire_and_forget' presente en el código de whatsapp.py "
        "(comentarios y docstrings ya excluidos del escaneo)."
    )


def test_background_tasks_delegation_is_confined_to_sanctioned_targets():
    """
    Pin de confinamiento: `background_tasks.add_task` solo puede apuntar a los
    targets sancionados (statuses / ingesta del mensaje). Cualquier NUEVA
    delegación background dentro del embudo comercial rompe este pin y exige
    aprobación explícita del Auditor.
    """
    tree = ast.parse(WHATSAPP_PY.read_text(encoding="utf-8"))
    delegated = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "add_task" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Name):
                    delegated.append((first.id, node.lineno))
    targets = {name for name, _ in delegated}
    assert targets <= SANCTIONED_ADD_TASK_TARGETS, (
        f"Delegación background NO sancionada detectada: {sorted(targets - SANCTIONED_ADD_TASK_TARGETS)}. "
        f"Sitios: {delegated}. Sancionados: {sorted(SANCTIONED_ADD_TASK_TARGETS)}."
    )
    assert len(delegated) == 3, (
        f"Comportamiento vigente alterado: se esperaban exactamente 3 sitios "
        f"add_task sancionados (statuses ×2, ingesta ×1), hallados: {delegated}"
    )


def test_background_tasks_delegation_is_confined_to_sanctioned_targets():
    """
    Pin de confinamiento: `background_tasks.add_task` solo puede apuntar a los
    targets sancionados (statuses / ingesta del mensaje). Cualquier NUEVA
    delegación background dentro del embudo comercial rompe este pin y exige
    aprobación explícita del Auditor.
    """
    tree = ast.parse(WHATSAPP_PY.read_text(encoding="utf-8"))
    delegated = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "add_task" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Name):
                    delegated.append((first.id, node.lineno))
    targets = {name for name, _ in delegated}
    assert targets <= SANCTIONED_ADD_TASK_TARGETS, (
        f"Delegación background NO sancionada detectada: {sorted(targets - SANCTIONED_ADD_TASK_TARGETS)}. "
        f"Sitios: {delegated}. Sancionados: {sorted(SANCTIONED_ADD_TASK_TARGETS)}."
    )
    assert len(delegated) == 3, (
        f"Comportamiento vigente alterado: se esperaban exactamente 3 sitios "
        f"add_task sancionados (statuses ×2, ingesta ×1), hallados: {delegated}"
    )
