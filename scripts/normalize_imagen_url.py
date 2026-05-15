#!/usr/bin/env python3
"""
=============================================================================
BOT-DB-4.3 — Script de Normalización de Schema: imagen_url
=============================================================================
OBJETIVO:
    Recorrer la sub-colección 'pagina/catalogo/items', extraer la URL de
    imagen válida (Firebase Storage) desde cualquier llave legacy, escribir
    la llave canónica 'imagen_url' como String, y eliminar llaves obsoletas
    ('imagenUrl', 'galeria', 'foto') para eliminar colisiones en CatalogService.

PRERREQUISITO (Ticket 4.2):
    Este script DEBE ejecutarse ANTES del despliegue del backend 4.2.

MODO DE EJECUCIÓN:
    --dry-run   (default): Audita sin escribir. Muestra plan de cambios.
    --execute   : Aplica cambios reales a Firestore. Requiere confirmación.

CERTIFICACIÓN REQUERIDA:
    100% de documentos activos con 'imagen_url' tipo String tras ejecución.
=============================================================================
"""
import argparse
import json
import logging
import os
import sys
from typing import Any, Optional

# ─── Configuración de logs estructurados (Mandato FASE 8: Zero-Silent-Failures)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("normalize_imagen_url")

# ─── Llaves legacy a BORRAR (MANDATO BOT-DB-4.3)
LEGACY_KEYS_TO_DELETE = ["imagenUrl", "galeria", "foto"]

# ─── Campos candidatos para extraer la URL, en orden de prioridad
CANDIDATE_FIELDS = ["imagen_url", "imagenUrl", "imagen", "foto", "image"]

# ─── Dominio válido para imágenes (Guardrail: Solo Firebase Storage)
VALID_IMAGE_DOMAIN = "firebasestorage.googleapis.com"


# =============================================================================
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN
# Implementa la lógica forense del CatalogService (L101-L120) para ser
# consistente con el contrato de lectura y evitar regresiones.
# =============================================================================
def _extract_valid_firebase_url(data: dict[str, Any]) -> Optional[str]:
    """
    Extrae la primera URL válida de Firebase Storage desde los campos candidatos.
    Maneja String, List[String] y Map{url: String} (patrón imagenUrl legacy).

    Returns:
        str: URL limpia si existe. None si no hay ninguna válida.
    """
    for field in CANDIDATE_FIELDS:
        val = data.get(field)
        if not val:
            continue

        raw: str = ""

        if isinstance(val, str):
            raw = val.strip()

        elif isinstance(val, list):
            # Patrón: galería como lista de URLs
            for item in val:
                if isinstance(item, str) and item.strip():
                    raw = item.strip()
                    break

        elif isinstance(val, dict):
            # Patrón legacy: imagenUrl como Map con sub-campo 'url'
            # Este es el caso confirmado en la arqueología de 390_duke_ng
            raw = str(val.get("url", "")).strip()

        if raw and VALID_IMAGE_DOMAIN in raw:
            return raw

    return None


# =============================================================================
# MOTOR DE NORMALIZACIÓN
# =============================================================================
def normalize_catalog(dry_run: bool = True) -> dict:
    """
    Motor principal de normalización. Recorre todos los documentos de
    'pagina/catalogo/items', audita y (si --execute) corrige el esquema.

    Returns:
        dict: Reporte de certificación con contadores y lista de fallos.
    """
    # ─── Inicialización del cliente de Firestore
    # Orden de prioridad: KEY_FILE env var > key.json en raíz del proyecto
    key_file = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        os.path.join(os.path.dirname(__file__), "..", "key.json"),
    )

    if not os.path.exists(key_file):
        logger.error(
            f"❌ CREDENCIALES NO ENCONTRADAS: {key_file}\n"
            "   Solución: Establece GOOGLE_APPLICATION_CREDENTIALS o coloca key.json en la raíz."
        )
        sys.exit(1)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_file
    logger.info(f"🔑 Usando credenciales: {key_file}")

    from google.cloud import firestore

    db = firestore.Client()

    mode_label = "DRY-RUN (sin cambios)" if dry_run else "⚠️  EJECUCIÓN REAL (Firestore será modificado)"
    logger.info(f"🚀 Iniciando BOT-DB-4.3 — Modo: {mode_label}")
    logger.info("📍 Colección destino: projects/tiendalasmotos/.../pagina/catalogo/items")

    items_ref = db.collection("pagina").document("catalogo").collection("items")
    docs = list(items_ref.stream())

    logger.info(f"📊 Total documentos encontrados: {len(docs)}")

    # ─── Contadores para el reporte de certificación
    total = len(docs)
    already_ok = 0          # Documentos que ya tenían imagen_url String válida
    fixed = 0               # Documentos normalizados en esta ejecución
    no_image_found = 0      # Documentos sin ninguna URL Firebase válida
    errors = 0              # Errores de escritura en Firestore
    failed_docs = []        # IDs de documentos sin imagen válida (para auditoría)
    plan_log = []           # Log de cambios planeados (para dry-run)

    for doc in docs:
        doc_id = doc.id
        data = doc.to_dict()

        # ─── Verificar si ya está normalizado (imagen_url String válida)
        existing = data.get("imagen_url")
        if isinstance(existing, str) and existing.strip() and VALID_IMAGE_DOMAIN in existing:
            already_ok += 1
            logger.info(f"  ✅ [{doc_id}] — Ya normalizado. imagen_url OK.")
            continue

        # ─── Extraer URL válida desde campos candidatos/legacy
        extracted_url = _extract_valid_firebase_url(data)

        if not extracted_url:
            no_image_found += 1
            failed_docs.append({"id": doc_id, "reason": "No Firebase Storage URL found"})
            logger.warning(
                f"  ⚠️  [{doc_id}] — SIN URL FIREBASE VÁLIDA. "
                f"Campos disponibles: {[k for k in data.keys() if 'image' in k.lower() or 'imagen' in k.lower() or 'foto' in k.lower() or 'galeria' in k.lower()]}"
            )
            continue

        # ─── Plan de cambios para este documento
        keys_to_delete = [k for k in LEGACY_KEYS_TO_DELETE if k in data]
        plan = {
            "doc_id": doc_id,
            "set": {"imagen_url": extracted_url},
            "delete": keys_to_delete,
            "source_field": next(
                (f for f in CANDIDATE_FIELDS if data.get(f) is not None), "unknown"
            ),
        }
        plan_log.append(plan)
        logger.info(
            f"  🔧 [{doc_id}] — imagen_url extraída desde '{plan['source_field']}'. "
            f"Llaves a borrar: {keys_to_delete}"
        )

        if dry_run:
            logger.info(f"     [DRY-RUN] URL que se escribiría: {extracted_url[:80]}...")
            fixed += 1  # Contamos como "fijaría" para el reporte
            continue

        # ─── Escritura ATÓMICA: set imagen_url + delete llaves legacy
        # Mandato FASE 3: Surgical Refactoring — solo los campos afectados
        try:
            update_payload: dict[str, Any] = {"imagen_url": extracted_url}

            # Marcar llaves legacy para eliminación con DELETE sentinel
            for legacy_key in keys_to_delete:
                update_payload[legacy_key] = firestore.DELETE_FIELD

            doc.reference.update(update_payload)
            fixed += 1
            logger.info(f"  ✅ [{doc_id}] — Normalizado y llaves legacy eliminadas.")

        except Exception as e:
            errors += 1
            failed_docs.append({"id": doc_id, "reason": f"Firestore write error: {str(e)}"})
            # Mandato FASE 3: Zero-Silent-Failures — log forense obligatorio
            logger.exception(
                f"  ❌ [{doc_id}] — ERROR DE ESCRITURA EN FIRESTORE. Detalle:", exc_info=e
            )

    # =============================================================================
    # REPORTE DE CERTIFICACIÓN
    # =============================================================================
    report = {
        "mode": "DRY_RUN" if dry_run else "EXECUTED",
        "total_documents": total,
        "already_normalized": already_ok,
        "normalized_in_this_run": fixed,
        "no_image_url_found": no_image_found,
        "write_errors": errors,
        "certification_passed": (no_image_found == 0 and errors == 0),
        "failed_documents": failed_docs,
        "change_plan": plan_log if dry_run else [],
    }

    logger.info("\n" + "=" * 70)
    logger.info("📋 REPORTE DE CERTIFICACIÓN BOT-DB-4.3")
    logger.info("=" * 70)
    logger.info(f"  Modo              : {report['mode']}")
    logger.info(f"  Total documentos  : {total}")
    logger.info(f"  Ya normalizados   : {already_ok}")
    logger.info(f"  {'Normalizarían' if dry_run else 'Normalizados'}  : {fixed}")
    logger.info(f"  Sin URL Firebase  : {no_image_found}")
    logger.info(f"  Errores escritura : {errors}")
    logger.info(
        f"  CERTIFICACIÓN     : {'✅ APROBADA' if report['certification_passed'] else '❌ FALLIDA — Revisar failed_documents'}"
    )

    if failed_docs:
        logger.warning("\n⚠️  Documentos que requieren revisión manual:")
        for fd in failed_docs:
            logger.warning(f"    • {fd['id']}: {fd['reason']}")

    if dry_run and plan_log:
        logger.info(f"\n📝 Plan de cambios ({len(plan_log)} documentos):")
        for p in plan_log:
            logger.info(f"    • [{p['doc_id']}] fuente='{p['source_field']}' | borrar={p['delete']}")

    logger.info("=" * 70 + "\n")
    return report


# =============================================================================
# ENTRY POINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="BOT-DB-4.3: Normaliza el campo imagen_url en pagina/catalogo/items"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Audita sin escribir. DEFAULT. Muestra plan de cambios.",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Aplica cambios reales a Firestore. Requiere confirmación interactiva.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Omite confirmación interactiva (usar solo en CI/CD con revisión previa).",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Ruta para guardar el reporte de certificación como JSON.",
    )

    args = parser.parse_args()

    is_dry_run = not args.execute

    if not is_dry_run and not args.yes:
        print("\n" + "!" * 70)
        print("⚠️  ADVERTENCIA: Estás a punto de MODIFICAR Firestore en producción.")
        print("   Colección: pagina/catalogo/items")
        print("   Acción: Escribir 'imagen_url', borrar 'imagenUrl', 'galeria', 'foto'")
        print("!" * 70)
        confirm = input("\n¿Confirmas la ejecución? Escribe 'EJECUTAR' para continuar: ")
        if confirm.strip() != "EJECUTAR":
            logger.info("❌ Ejecución cancelada por el operador.")
            sys.exit(0)

    report = normalize_catalog(dry_run=is_dry_run)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Reporte JSON guardado en: {args.output_json}")

    # Exit code: 0 si certificación pasada, 1 si hay fallos
    sys.exit(0 if report["certification_passed"] else 1)


if __name__ == "__main__":
    main()
