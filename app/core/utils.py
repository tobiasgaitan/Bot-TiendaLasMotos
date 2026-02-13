"""
Core Utilities
"""
import re

class PhoneNormalizer:
    """
    Standardizes phone numbers to a consistent format (10-digit national).
    
    Format target: 3XXXXXXXXX (National format, no country code).
    Use cases:
    - Firestore Document IDs (Uniqueness)
    - Database queries (Consistency)
    - System-internal references
    
    This class ensures that "57319..." and "319..." map to the same entity.
    """
    
    @staticmethod
    def normalize(phone: str) -> str:
        """
        Convert any phone format to 10-digit national format.
        
        Args:
            phone: Raw phone string (e.g. "+57 319-256-4288", "573192564288")
            
        Returns:
            10-digit string (e.g. "3192564288") or original if length < 10
        """
        # 1. Remove all non-numeric characters
        clean = re.sub(r'\D', '', str(phone))
        
        # 2. Strip Colombia country code (57) if present at start
        # Only valid for mobile numbers which are usually 10 digits
        # So 57 + 10 digits = 12 digits. But we accept 11 too (57+9) just in case.
        if clean.startswith('57') and len(clean) > 10:
            clean = clean[2:]
            
        return clean

    @staticmethod
    def to_international(phone: str) -> str:
        """
        Convert to strictly international format (573XXXXXXXXX) for WhatsApp API.
        
        Args:
            phone: Normalized or raw phone
            
        Returns:
            12-digit string starting with 57
        """
        check = PhoneNormalizer.normalize(phone)
        if len(check) == 10:
            return f"57{check}"
        return check
