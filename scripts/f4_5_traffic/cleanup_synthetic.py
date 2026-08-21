#!/usr/bin/env python3
"""
BOT-BUILD-F45-TRAFFIC-087 — Limpieza de prospectos sintéticos.

Dry-run por defecto. Con --execute elimina recursivamente los documentos de
`prospectos` cuyo id comience por +5737700 (prefijo reservado F4.5).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import firebase_admin
from firebase_admin import credentials, firestore

SYNTHETIC_PREFIX = "+5737700"
BATCH_SIZE = 50


def delete_collection_recursively(coll_ref, batch_size: int = BATCH_SIZE) -> int:
    """Elimina todos los documentos de una subcolección, incluyendo subcolecciones anidadas."""
    deleted = 0
    docs = list(coll_ref.limit(batch_size).stream())
    while docs:
        for doc in docs:
            deleted += delete_doc_recursively(doc.reference)
        docs = list(coll_ref.limit(batch_size).stream())
    return deleted


def delete_doc_recursively(doc_ref) -> int:
    """Elimina un documento y todas sus subcolecciones."""
    deleted = 1
    for coll in doc_ref.collections():
        deleted += delete_collection_recursively(coll)
    doc_ref.delete()
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpieza de prospectos sintéticos F4.5")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar el borrado real (sin este flag es dry-run)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="tiendalasmotos",
        help="ID del proyecto GCP",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=SYNTHETIC_PREFIX,
        help="Prefijo E.164 de teléfonos sintéticos",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Listar los documentos que coinciden",
    )
    args = parser.parse_args()

    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"projectId": args.project})

    db = firestore.client()
    coll = db.collection("prospectos")

    print(f"🔍 Escaneando 'prospectos' con prefijo {args.prefix}...")
    matching: List[firestore.DocumentSnapshot] = []
    for doc in coll.stream():
        if doc.id.startswith(args.prefix):
            matching.append(doc)

    print(f"   Encontrados {len(matching)} documentos sintéticos.")

    if args.list:
        for doc in matching:
            data = doc.to_dict() or {}
            print(f"   - {doc.id} => celular={data.get('celular', 'N/A')}, nombre={data.get('nombre', 'N/A')}")

    if not args.execute:
        print("\n🔒 DRY-RUN: no se borró nada.")
        print("   Ejecuta con --execute para purgar.")
        return 0

    if not matching:
        print("✅ No hay documentos que borrar.")
        return 0

    print(f"\n🚀 Borrando {len(matching)} documentos recursivamente...")
    total_deleted = 0
    for idx, doc in enumerate(matching, 1):
        total_deleted += delete_doc_recursively(doc.reference)
        if idx % 10 == 0:
            print(f"   {idx}/{len(matching)} procesados...")

    print(f"✅ Purga completa: {total_deleted} documentos/subcolecciones eliminados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
