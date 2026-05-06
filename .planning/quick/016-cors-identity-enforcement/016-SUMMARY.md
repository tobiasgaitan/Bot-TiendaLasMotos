# Quick Task 016: CORS & Identity Enforcement — Summary

**Executed:** 2026-05-06
**Status:** Complete

## What Was Done

### 1. CORS Fix (main.py)
- Replaced illegal `allow_origins=["*"]` with explicit whitelist:
  - `https://tiendalasmotos-beta.web.app`
  - `https://tiendalasmotos.com`
  - `http://localhost:3000`
- Added documentation explaining WHY wildcard + credentials is illegal per CORS spec

### 2. PhoneNormalizer Refactor (utils.py)
- **Purged** `to_international()` method entirely
- Updated class docstring to reflect E.164 contract (`+57XXXXXXXXXX`)
- Removed stale docstring references to "10-digit national format"

### 3. WhatsApp Service Transport Fix (whatsapp_service.py)
- Replaced 3 calls to `PhoneNormalizer.to_international(x)` with `PhoneNormalizer.normalize(x).lstrip("+")`
- Meta API receives digits-only format (`573192564288`) stripped at the transport boundary
- Internal canonical format remains E.164 (`+573192564288`)

### 4. Admin API & Survey Service (NO CHANGES NEEDED)
- Verified that `admin.py` and `survey_service.py` already use `PhoneNormalizer.normalize()` for Firestore Document IDs (patched in Quick Task 015, commit b71cc20)

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| app/main.py | Modified | CORS explicit origins whitelist |
| app/core/utils.py | Modified | Purged to_international(), updated E.164 docstrings |
| app/services/whatsapp_service.py | Modified | 3x to_international → normalize().lstrip("+") |

## Verification
| Check | Result |
|-------|--------|
| `grep "allow_origins" app/main.py` | ✅ Line 130: explicit list, no wildcard |
| `grep -rn "to_international" app/` | ✅ Zero source matches (only stale .pyc) |
| `normalize("3192564288")` | ✅ `+573192564288` |
| `normalize("573192564288")` | ✅ `+573192564288` (idempotent) |
| `.lstrip("+")` | ✅ `573192564288` (Meta wire format) |
| Stale `.pyc` cache | ✅ Purged |

---
*Completed: 2026-05-06*
