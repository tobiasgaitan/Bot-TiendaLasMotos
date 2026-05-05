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
        Convert any phone format to 12-digit international format.
        
        Args:
            phone: Raw phone string (e.g. "+57 319-256-4288", "3192564288")
            
        Returns:
            12-digit string starting with 57 (e.g. "573192564288")
        """
        # 1. Remove all non-numeric characters
        clean = re.sub(r'\D', '', str(phone))
        
        # 2. Add Colombia country code (57) if 10 digits
        if len(clean) == 10:
            clean = f"57{clean}"
            
        return f"+{clean}"

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
        return check.replace("+", "")
