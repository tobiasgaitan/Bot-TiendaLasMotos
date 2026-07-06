"""
Custom business exceptions for Bot-TiendaLasMotos.

WHY: Centralized exception definitions ensure that business-logic
interrupts (e.g., Habeas Data consent bypass) propagate cleanly
through the async call stack without being silenced by generic
`except Exception` blocks.
"""


class HabeasDataBypassInterrupt(Exception):
    """
    Señal de negocio que permite al bloque 'except PermissionError'
    en _generate_with_retry_async cortocircuitar limpiamente TODO el
    pipeline (including el while loop de pensar_respuesta) sin corromper
    el tipo de retorno ni disparar Phase-Gate/PCC validation.

    El string de respuesta se transporta en args[0].

    Ref: BOT-BRAIN-CRITICAL-E2E-084
    """
    pass
