#!/usr/bin/env python3
"""
Firestore Global Search & Destroy (Sherlock Script)
Finds and optionally deletes hidden records by phone number across ALL Firestore collections.

Usage:
    python3 scripts/buscar_y_destruir.py --number 573192564288
    python3 scripts/buscar_y_destruir.py --number 573192564288 --dry-run

Requirements:
    - firebase-admin installed
    - Application Default Credentials configured (gcloud auth application-default login)
    - Or running in Cloud Shell with appropriate permissions
"""

import argparse
import sys
import os
from typing import List, Dict, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import firebase_admin
from firebase_admin import credentials, firestore


# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def initialize_firebase() -> firestore.Client:
    """
    Initialize Firebase Admin SDK with Application Default Credentials.
    
    Returns:
        Firestore client instance
    
    Raises:
        SystemExit if initialization fails
    """
    try:
        # Use Application Default Credentials (works in Cloud Shell and local with gcloud auth)
        firebase_admin.initialize_app(credentials.ApplicationDefault(), {
            'projectId': 'tiendalasmotos',
        })
        print(f"{Colors.OKGREEN}✅ Firebase Admin initialized successfully{Colors.ENDC}")
        return firestore.client()
    except Exception as e:
        print(f"{Colors.FAIL}❌ Error initializing Firebase: {str(e)}{Colors.ENDC}")
        sys.exit(1)


def discover_collections(db: firestore.Client) -> List[str]:
    """
    List all root-level collections in the Firestore database.
    
    Args:
        db: Firestore client instance
    
    Returns:
        List of collection names
    """
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}🔍 DISCOVERING COLLECTIONS{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")
    
    collections = []
    for collection in db.collections():
        collections.append(collection.id)
        print(f"  📁 {collection.id}")
    
    print(f"\n{Colors.OKCYAN}Total collections found: {len(collections)}{Colors.ENDC}\n")
    return collections


def search_by_document_id(db: firestore.Client, collection_name: str, phone_number: str) -> Optional[Dict]:
    """
    Search for a document with ID matching the phone number.
    
    Args:
        db: Firestore client instance
        collection_name: Name of the collection to search
        phone_number: Phone number to search for
    
    Returns:
        Document data if found, None otherwise
    """
    try:
        doc_ref = db.collection(collection_name).document(phone_number)
        doc = doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"{Colors.WARNING}⚠️  Error searching by ID in {collection_name}: {str(e)}{Colors.ENDC}")
        return None


def search_by_fields(db: firestore.Client, collection_name: str, phone_number: str) -> List[Tuple[str, Dict]]:
    """
    Search for phone number in common phone fields.
    
    Args:
        db: Firestore client instance
        collection_name: Name of the collection to search
        phone_number: Phone number to search for
    
    Returns:
        List of tuples (document_id, document_data) for matches
    """
    # Common field names for phone numbers (Spanish and English)
    phone_fields = ['celular', 'phone', 'telefono', 'mobile', 'user_id', 'id']
    matches = []
    
    for field in phone_fields:
        try:
            query = db.collection(collection_name).where(field, '==', phone_number)
            results = query.get()
            
            for doc in results:
                matches.append((doc.id, doc.to_dict()))
        except Exception as e:
            # Some fields may not exist or may not be indexed - this is expected
            pass
    
    return matches


def highlight_status_fields(data: Dict) -> Tuple[bool, List[str]]:
    """
    Check if document contains human_handoff or paused status flags.
    
    Args:
        data: Document data dictionary
    
    Returns:
        Tuple of (has_status_flag, list_of_flagged_fields)
    """
    status_keywords = ['human_handoff', 'paused', 'PAUSED', 'HUMAN_HANDOFF']
    flagged_fields = []
    
    def check_value(value, field_path=""):
        """Recursively check nested values"""
        if isinstance(value, str):
            for keyword in status_keywords:
                if keyword.lower() in value.lower():
                    flagged_fields.append(f"{field_path} = {value}")
        elif isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{field_path}.{k}" if field_path else k)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(item, f"{field_path}[{i}]")
    
    check_value(data)
    return len(flagged_fields) > 0, flagged_fields


def display_result(collection_name: str, doc_id: str, data: Dict, has_status: bool, flagged_fields: List[str]):
    """
    Pretty print search result with highlighting.
    
    Args:
        collection_name: Name of the collection
        doc_id: Document ID
        data: Document data
        has_status: Whether document has status flags
        flagged_fields: List of fields with status flags
    """
    print(f"\n{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}✅ MATCH FOUND!{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}\n")
    
    print(f"{Colors.BOLD}Collection:{Colors.ENDC} {Colors.OKCYAN}{collection_name}{Colors.ENDC}")
    print(f"{Colors.BOLD}Document ID:{Colors.ENDC} {Colors.OKCYAN}{doc_id}{Colors.ENDC}\n")
    
    if has_status:
        print(f"{Colors.WARNING}⚠️  STATUS FLAGS DETECTED:{Colors.ENDC}")
        for field in flagged_fields:
            print(f"{Colors.WARNING}   🚨 {field}{Colors.ENDC}")
        print()
    
    print(f"{Colors.BOLD}Full Document Data:{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{'-' * 60}{Colors.ENDC}")
    for key, value in data.items():
        print(f"  {Colors.BOLD}{key}:{Colors.ENDC} {value}")
    print(f"{Colors.OKBLUE}{'-' * 60}{Colors.ENDC}\n")


def confirm_delete() -> bool:
    """
    Prompt user for delete confirmation.
    
    Returns:
        True if user confirms deletion, False otherwise
    """
    while True:
        response = input(f"{Colors.WARNING}Do you want to DELETE this document? (y/n): {Colors.ENDC}").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print(f"{Colors.FAIL}Invalid input. Please enter 'y' or 'n'.{Colors.ENDC}")


def delete_document(db: firestore.Client, collection_name: str, doc_id: str):
    """
    Delete document and confirm.
    
    Args:
        db: Firestore client instance
        collection_name: Name of the collection
        doc_id: Document ID to delete
    """
    try:
        db.collection(collection_name).document(doc_id).delete()
        print(f"\n{Colors.OKGREEN}✅ Document deleted successfully!{Colors.ENDC}")
        print(f"{Colors.OKGREEN}   Collection: {collection_name}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}   Document ID: {doc_id}{Colors.ENDC}\n")
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Error deleting document: {str(e)}{Colors.ENDC}\n")


def search_all_collections(db: firestore.Client, phone_number: str, dry_run: bool = False) -> int:
    """
    Search for phone number across all collections.
    
    Args:
        db: Firestore client instance
        phone_number: Phone number to search for
        dry_run: If True, don't offer deletion option
    
    Returns:
        Number of matches found
    """
    collections = discover_collections(db)
    total_matches = 0
    
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}🕵️  SEARCHING FOR: {phone_number}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")
    
    for collection_name in collections:
        print(f"Scanning collection: {collection_name}...", end='\r')
        
        # Strategy A: Search by Document ID
        doc_data = search_by_document_id(db, collection_name, phone_number)
        if doc_data:
            has_status, flagged_fields = highlight_status_fields(doc_data)
            display_result(collection_name, phone_number, doc_data, has_status, flagged_fields)
            total_matches += 1
            
            if not dry_run and confirm_delete():
                delete_document(db, collection_name, phone_number)
        
        # Strategy B: Search by common phone fields
        field_matches = search_by_fields(db, collection_name, phone_number)
        for doc_id, doc_data in field_matches:
            # Skip if we already found this as a document ID match
            if doc_id == phone_number and total_matches > 0:
                continue
            
            has_status, flagged_fields = highlight_status_fields(doc_data)
            display_result(collection_name, doc_id, doc_data, has_status, flagged_fields)
            total_matches += 1
            
            if not dry_run and confirm_delete():
                delete_document(db, collection_name, doc_id)
    
    # Clear the "Scanning..." line
    print(" " * 80, end='\r')
    
    return total_matches


def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
    
    Returns:
        True if valid, False otherwise
    """
    # Must be numeric and between 10-12 digits
    if not phone.isdigit():
        return False
    if len(phone) < 10 or len(phone) > 12:
        return False
    return True


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Firestore Global Search & Destroy - Find and delete hidden records by phone number',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/buscar_y_destruir.py --number 573192564288
  python3 scripts/buscar_y_destruir.py --number 573192564288 --dry-run
        """
    )
    parser.add_argument(
        '--number',
        required=True,
        help='Phone number to search for (10-12 digits)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Search only, do not offer deletion option'
    )
    
    args = parser.parse_args()
    
    # Validate phone number
    if not validate_phone_number(args.number):
        print(f"{Colors.FAIL}❌ Invalid phone number format. Must be 10-12 digits.{Colors.ENDC}")
        sys.exit(1)
    
    print(f"\n{Colors.BOLD}🚀 Firestore Global Search & Destroy{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"Project: {Colors.OKCYAN}tiendalasmotos{Colors.ENDC}")
    print(f"Phone Number: {Colors.OKCYAN}{args.number}{Colors.ENDC}")
    print(f"Mode: {Colors.OKCYAN}{'DRY RUN (Read-Only)' if args.dry_run else 'SEARCH & DESTROY'}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")
    
    # Initialize Firebase
    db = initialize_firebase()
    
    # Search all collections
    total_matches = search_all_collections(db, args.number, args.dry_run)
    
    # Final report
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}📊 SEARCH COMPLETE{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")
    
    if total_matches == 0:
        print(f"{Colors.WARNING}No matches found for phone number: {args.number}{Colors.ENDC}")
        print(f"{Colors.WARNING}The record may have already been deleted or doesn't exist.{Colors.ENDC}\n")
    else:
        print(f"{Colors.OKGREEN}Total matches found: {total_matches}{Colors.ENDC}\n")
    
    print(f"{Colors.OKGREEN}✅ Script completed successfully!{Colors.ENDC}\n")


if __name__ == "__main__":
    main()
