#!/usr/bin/env python3
"""
Prospect Normalization & Deduplication Script
=============================================
Scans the 'prospectos' collection, normalizes all phone numbers to 10-digit format,
merges duplicate records, and deletes the old ones.

Usage:
    python3 scripts/normalize_deduplicate_prospects.py --dry-run
    python3 scripts/normalize_deduplicate_prospects.py --execute

Requires:
    - firebase-admin
    - Application Default Credentials
"""

import sys
import os
import argparse
from typing import Dict, List, Any
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import firebase_admin
from firebase_admin import credentials, firestore
from app.core.utils import PhoneNormalizer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("migration")

class Colors:
    HEADER = '\033[95m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def initialize_firebase():
    try:
        firebase_admin.initialize_app(credentials.ApplicationDefault(), {
            'projectId': 'tiendalasmotos',
        })
        return firestore.client()
    except Exception as e:
        logger.error(f"Failed to init Firebase: {e}")
        sys.exit(1)

def merge_documents(docs: List[Any], normalized_phone: str) -> Dict[str, Any]:
    """
    Merge multiple prospect documents into a single canonical record.
    Priority:
    - Name: Longest non-empty
    - Moto: Most recent (mock logic: non-empty)
    - Summary: Concatenated (newest first)
    - Human Help: OR (if any is True, result is True)
    - Timestamps: MAX
    """
    merged = {
        "celular": normalized_phone,
        "nombre": "",
        "motoInteres": "",
        "ai_summary": "",
        "human_help_requested": False,
        "chatbot_status": "ACTIVE",
        "created_at": None,
        "updated_at": None,
        "fecha": None
    }
    
    summaries = []
    
    for doc in docs:
        data = doc.to_dict()
        
        # Name: Keep longest
        name = data.get("nombre", "")
        if name and len(name) > len(merged["nombre"]):
            merged["nombre"] = name
            
        # Moto: Keep longest/most specific
        moto = data.get("motoInteres", "")
        if moto and len(moto) > len(merged["motoInteres"]):
            merged["motoInteres"] = moto
            
        # Human Help: OR logic (safety)
        if data.get("human_help_requested"):
            merged["human_help_requested"] = True
            
        # Summary: Collect all non-empty
        summary = data.get("ai_summary", "")
        if summary:
            summaries.append(f"[{doc.id}]: {summary}")
            
        # Timestamps: Keep latest
        for ts_field in ["created_at", "updated_at", "fecha"]:
            val = data.get(ts_field)
            if val:
                if merged[ts_field] is None or (hasattr(val, 'timestamp') and hasattr(merged[ts_field], 'timestamp') and val.timestamp() > merged[ts_field].timestamp()):
                    merged[ts_field] = val
                elif not merged[ts_field]: # If existing is None
                    merged[ts_field] = val

    # Merge summaries
    if summaries:
        merged["ai_summary"] = "\n\n-- MERGED --\n\n".join(summaries)
        
    return merged

def main():
    parser = argparse.ArgumentParser(description="Normalize and Deduplicate Prospects")
    parser.add_argument("--execute", action="store_true", help="Perform actual writes/deletes")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without changes")
    args = parser.parse_args()
    
    if not args.execute and not args.dry_run:
        print("Please specify --execute or --dry-run")
        sys.exit(1)
        
    db = initialize_firebase()
    
    print(f"{Colors.HEADER}Scanning 'prospectos' collection...{Colors.ENDC}")
    all_docs = list(db.collection("prospectos").stream())
    print(f"Found {len(all_docs)} total documents.")
    
    # Group by normalized phone
    grouped = {}
    for doc in all_docs:
        # Use 'celular' field as primary source, ID as secondary
        # The ID might be auto-generated (random) or a phone number.
        # The 'celular' field typically contains the actual phone.
        data = doc.to_dict()
        raw_field = data.get("celular", "")
        raw_id = doc.id
        
        # Determine the best source for the phone number
        source_val = str(raw_field) if raw_field else raw_id
        
        # Normalize to get the grouping key
        norm = PhoneNormalizer.normalize(source_val)
        
        # Skip invalid/empty normalizations (e.g. from purely random IDs without digits)
        if not norm:
            continue
            
        if norm not in grouped:
            grouped[norm] = []
        grouped[norm].append(doc)
        
    duplicates_found = 0
    records_to_migrate = 0
    
    print(f"\n{Colors.BOLD}Analysis results:{Colors.ENDC}")
    
    for norm_phone, docs in grouped.items():
        is_duplicate = len(docs) > 1
        needs_migration = len(docs) == 1 and docs[0].id != norm_phone
        
        if is_duplicate or needs_migration:
            if is_duplicate:
                duplicates_found += 1
                status = f"{Colors.FAIL}DUPLICATE ({len(docs)}){Colors.ENDC}"
            else:
                records_to_migrate += 1
                status = f"{Colors.WARNING}MIGRATE ID{Colors.ENDC}"
                
            print(f"Phone: {norm_phone} -> {status}")
            for d in docs:
                print(f"   - {d.id} (celular: {d.to_dict().get('celular')})")
            
            # Logic
            merged_data = merge_documents(docs, norm_phone)
            
            if args.execute:
                batch = db.batch()
                
                # 1. Create/Update Canonical Doc
                target_ref = db.collection("prospectos").document(norm_phone)
                batch.set(target_ref, merged_data, merge=True)
                
                # 2. Delete non-canonical docs
                for d in docs:
                    if d.id != norm_phone:
                        batch.delete(d.reference)
                        print(f"     🗑️  Deleting {d.id}")
                
                batch.commit()
                print(f"     ✅ Merged & Saved to {norm_phone}")
                
    print(f"\n{Colors.HEADER}Summary:{Colors.ENDC}")
    print(f"Total Unique Phones: {len(grouped)}")
    print(f"Duplicate Groups: {duplicates_found}")
    print(f"ID Migrations Needed: {records_to_migrate}")
    
    if args.dry_run:
        print(f"\n{Colors.OKGREEN}Dry run complete. No changes made.{Colors.ENDC}")
        print("Run with --execute to apply changes.")
    else:
        print(f"\n{Colors.OKGREEN}Migration complete!{Colors.ENDC}")

if __name__ == "__main__":
    main()
