"""
Test Phone Normalization Logic
Verifies the PhoneNormalizer utility class.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.utils import PhoneNormalizer

def test_phone_normalization():
    """Test the PhoneNormalizer utility."""
    
    test_cases_normalize = [
        # (input, expected)
        ("573192564288", "3192564288"),
        ("+573192564288", "3192564288"),
        ("3192564288", "3192564288"),
        ("+57300123456", "300123456"),
        ("57123", "57123"), # Too short to strip prefix
        ("   300 123-4567  ", "3001234567"),
        ("+57 319-256-4288", "3192564288")
    ]
    
    print("=" * 70)
    print("PHONE NORMALIZER UTILITY TEST")
    print("=" * 70)
    
    print("\n🔹 Testing normalize()...")
    for input_phone, expected in test_cases_normalize:
        result = PhoneNormalizer.normalize(input_phone)
        print(f"   Input: '{input_phone}' -> Result: '{result}' (Expected: '{expected}')")
        assert result == expected, f"❌ Failed! Got {result}, expected {expected}"
        print(f"   ✅ PASS")

    print("\n🔹 Testing to_international()...")
    test_cases_intl = [
        ("3192564288", "573192564288"),
        ("573192564288", "573192564288"),
        ("123", "123") # Should return as is if not 10 digits
    ]
    for input_phone, expected in test_cases_intl:
        result = PhoneNormalizer.to_international(input_phone)
        print(f"   Input: '{input_phone}' -> Result: '{result}' (Expected: '{expected}')")
        assert result == expected, f"❌ Failed! Got {result}, expected {expected}"
        print(f"   ✅ PASS")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)

if __name__ == "__main__":
    test_phone_normalization()
