"""Declaraciones de herramientas reales del sistema para China Eval."""
from __future__ import annotations


def search_catalog_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": (
                "Busca motos en el catálogo por estilo, modelo, marca o texto libre. "
                "Devuelve nombre_moto, precio numérico, imagen_url y descripción."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "estilo": {
                        "type": "string",
                        "enum": ["Automática", "Deportiva", "Motocarro", "Semiautomática", "Scooter"],
                        "description": "Estilo de moto",
                    },
                    "modelo": {"type": "string", "description": "Modelo exacto o referencia"},
                    "marca": {"type": "string", "description": "Marca de la moto"},
                    "searchBy": {"type": "string", "description": "Texto libre de búsqueda"},
                },
                "anyOf": [
                    {"required": ["estilo"]},
                    {"required": ["modelo"]},
                    {"required": ["marca"]},
                    {"required": ["searchBy"]},
                ],
            },
        },
    }


def calculate_credit_score_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "calculate_credit_score",
            "description": (
                "Calcula score crediticio para financiación con Brilla de Gases. "
                "Recibe datos del perfilamiento y devuelve JSON con score numérico, "
                "entidad, cuota y plazo. Score es solo lectura interna."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entidad": {"type": "string"},
                    "ocupacion_y_contrato": {"type": "string"},
                    "ingresos_demostrables": {"type": "string"},
                    "historial_datacredito": {"type": "string"},
                    "plan_celular": {"type": "string"},
                    "reportes": {"type": "string"},
                    "inicial": {"type": "string"},
                    "gastos": {"type": "string"},
                    "gas_natural": {"type": "string"},
                    "vivienda": {"type": "string"},
                },
                "required": ["entidad", "ocupacion_y_contrato", "ingresos_demostrables"],
            },
        },
    }


def query_faq_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "query_faq",
            "description": "Responde preguntas generales de crédito (codeudores, reportes, inicial).",
            "parameters": {
                "type": "object",
                "properties": {"pregunta": {"type": "string"}},
                "required": ["pregunta"],
            },
        },
    }


def query_locations_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "query_locations",
            "description": "Devuelve ubicaciones de las 5 sedes (Santa Marta ×3, Riohacha, Zona Bananera).",
            "parameters": {
                "type": "object",
                "properties": {"ciudad": {"type": "string"}},
                "required": ["ciudad"],
            },
        },
    }


ALL_TOOLS = [search_catalog_tool(), calculate_credit_score_tool(), query_faq_tool(), query_locations_tool()]
