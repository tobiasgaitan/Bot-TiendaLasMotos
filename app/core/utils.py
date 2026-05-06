"""
Core Utilities
"""
import re

class PhoneNormalizer:
    """
    Standardizes phone numbers to E.164 international format.
    
    Format target: +57XXXXXXXXXX (E.164 with Colombia country code).
    Use cases:
    - Firestore Document IDs (Uniqueness)
    - Database queries (Consistency)
    - System-internal references
    - WhatsApp API transport (strip '+' at call site)
    
    This class ensures that "57319..." and "319..." map to the same entity.
    
    Contract (BOT-FIX-902):
        normalize("3192564288")   -> "+573192564288"
        normalize("+573192564288") -> "+573192564288"
        normalize("573192564288")  -> "+573192564288"
    """
    
    @staticmethod
    def normalize(phone: str) -> str:
        """
        Convert any phone format to E.164 international format.
        
        Args:
            phone: Raw phone string (e.g. "+57 319-256-4288", "3192564288")
            
        Returns:
            E.164 string with '+' prefix (e.g. "+573192564288")
        """
        # 1. Remove all non-numeric characters
        clean = re.sub(r'\D', '', str(phone))
        
        # 2. Add Colombia country code (57) if 10 digits
        if len(clean) == 10:
            clean = f"57{clean}"
            
        return f"+{clean}"
