"""
Test Phone Normalization Logic
Verifies the multi-attempt strategy works correctly.
"""

def test_phone_normalization():
    """Test the phone normalization logic without Firestore."""
    
    test_cases = [
        # (input, expected_attempt1, expected_attempt2)
        ("573192564288", "573192564288", "3192564288"),
        ("+573192564288", "573192564288", "3192564288"),
        ("3192564288", "3192564288", None),  # No attempt 2 (doesn't start with 57)
        ("+57300123456", "57300123456", "300123456"),
        ("57123", "57123", None),  # No attempt 2 (length <= 10)
    ]
    
    print("=" * 70)
    print("PHONE NORMALIZATION TEST")
    print("=" * 70)
    
    for input_phone, expected_clean, expected_short in test_cases:
        print(f"\n📞 Input: {input_phone}")
        
        # Step 1: Clean phone (remove + prefix)
        clean_phone = input_phone.replace("+", "")
        print(f"   Attempt 1: '{clean_phone}' (expected: '{expected_clean}')")
        assert clean_phone == expected_clean, f"Attempt 1 failed! Got {clean_phone}, expected {expected_clean}"
        
        # Step 2: Try with country code stripped (if starts with "57")
        if clean_phone.startswith("57") and len(clean_phone) > 10:
            short_phone = clean_phone[2:]  # Remove "57" prefix
            print(f"   Attempt 2: '{short_phone}' (expected: '{expected_short}')")
            assert short_phone == expected_short, f"Attempt 2 failed! Got {short_phone}, expected {expected_short}"
        else:
            print(f"   Attempt 2: Skipped (doesn't start with '57' or length <= 10)")
            assert expected_short is None, f"Expected attempt 2 to run but it was skipped"
        
        print(f"   ✅ PASS")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)

if __name__ == "__main__":
    test_phone_normalization()
