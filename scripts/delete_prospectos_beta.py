#!/usr/bin/env python3
"""
Prospectos Beta Cleanup Script
==============================
Deletes all documents in the 'prospectos_beta' collection to clean up the ghost collection.

Usage:
    python3 scripts/delete_prospectos_beta.py --execute

Requires:
    - firebase-admin
    - Application Default Credentials
"""

import sys
import os
import argparse
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import firebase_admin
from firebase_admin import credentials, firestore

def delete_collection(coll_ref, batch_size):
    """
    Deletes all documents in a collection in batches.
    """
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        print(f"Deleting doc {doc.id} => {doc.to_dict().get('celular', 'No phone')}")
        doc.reference.delete()
        deleted += 1

    if deleted >= batch_size:
        return deleted + delete_collection(coll_ref, batch_size)

    return deleted

def main():
    parser = argparse.ArgumentParser(description="Clean up the ghost collection 'prospectos_beta'")
    parser.add_argument("--execute", action="store_true", help="Actually delete the documents (otherwise just dry-run)")
    args = parser.parse_args()

    print("Initializing Firebase Admin SDK...")
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Not initialized, initialize using Application Default Credentials
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': 'tiendalasmotos',
        })

    db = firestore.client()
    beta_ref = db.collection("prospectos_beta")
    
    if args.execute:
        print("🚀 Executing deletion of 'prospectos_beta' collection...")
        deleted_count = delete_collection(beta_ref, 50)
        print(f"✅ Successfully deleted {deleted_count} documents from 'prospectos_beta'.")
    else:
        print("🔍 DRY RUN: Scanning 'prospectos_beta' collection...")
        docs = list(beta_ref.stream())
        print(f"Found {len(docs)} documents in 'prospectos_beta'.")
        if docs:
            print("Run with --execute to permanently delete them.")
        else:
            print("Collection is already empty.")

if __name__ == "__main__":
    main()
