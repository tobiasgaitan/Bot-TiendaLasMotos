# 🕵️ Firestore Search & Destroy Script - Usage Guide

## Overview

The `buscar_y_destruir.py` (Search & Destroy) script is a diagnostic tool designed to find hidden records in Firestore that may be blocking the WhatsApp bot due to persistent `human_handoff` or `PAUSED` status flags.

## Problem It Solves

When a phone number is locked out of the bot with a `human_handoff` status, but you can't find the record in known collections (`prospectos`, `users`), this script will:

1. 🔍 **Scan ALL collections** in your Firestore database
2. 🎯 **Search by multiple strategies** (Document ID + 6 common phone field names)
3. ⚠️ **Highlight status flags** (`human_handoff`, `PAUSED`)
4. 🗑️ **Offer safe deletion** with confirmation prompts

## Prerequisites

### 1. Authentication Setup

You must have Application Default Credentials configured:

```bash
# Option A: Using gcloud CLI (recommended for local development)
gcloud auth application-default login

# Option B: In Cloud Shell (already authenticated)
# No additional setup needed
```

### 2. Required Permissions

Your account needs Firestore read/write permissions:
- `datastore.entities.get`
- `datastore.entities.list`
- `datastore.entities.delete`

## Usage

### Basic Search & Destroy

```bash
python3 scripts/buscar_y_destruir.py --number 573192564288
```

This will:
- Search all collections for the phone number
- Display any matches with full document data
- Highlight any `human_handoff` or `PAUSED` flags
- Prompt for deletion confirmation for each match

### Dry Run (Read-Only Mode)

```bash
python3 scripts/buscar_y_destruir.py --number 573192564288 --dry-run
```

This will:
- Search all collections (same as above)
- Display matches
- **NOT offer deletion option** (safe for diagnostics)

### Help

```bash
python3 scripts/buscar_y_destruir.py --help
```

## How It Works

### Dual Search Strategy

The script uses two complementary search methods:

#### Strategy A: Document ID Match
```python
# Checks if the phone number is used as a Document ID
collection.document("573192564288").get()
```

#### Strategy B: Field-Based Queries
```python
# Queries 6 common phone field names:
fields = ['celular', 'phone', 'telefono', 'mobile', 'user_id', 'id']
collection.where(field, '==', "573192564288")
```

### Status Flag Detection

The script recursively searches document data for these keywords:
- `human_handoff`
- `HUMAN_HANDOFF`
- `paused`
- `PAUSED`

If found, they are highlighted in **yellow** with a 🚨 warning icon.

## Output Example

```
🚀 Firestore Global Search & Destroy
============================================================
Project: tiendalasmotos
Phone Number: 573192564288
Mode: SEARCH & DESTROY
============================================================

✅ Firebase Admin initialized successfully

============================================================
🔍 DISCOVERING COLLECTIONS
============================================================

  📁 prospectos
  📁 users
  📁 catalog_items
  📁 audit_logs

Total collections found: 4

============================================================
🕵️  SEARCHING FOR: 573192564288
============================================================

============================================================
✅ MATCH FOUND!
============================================================

Collection: prospectos
Document ID: 573192564288

⚠️  STATUS FLAGS DETECTED:
   🚨 chatbot_status = human_handoff

Full Document Data:
------------------------------------------------------------
  celular: 573192564288
  nombre: Juan Pérez
  chatbot_status: human_handoff
  ai_summary: Cliente solicitó hablar con humano
  created_at: 2026-02-05 10:30:00
------------------------------------------------------------

Do you want to DELETE this document? (y/n): 
```

## Safety Features

### ✅ Confirmation Required
- Each deletion requires explicit `y/n` confirmation
- No batch deletions - one document at a time

### ✅ Full Data Display
- Shows complete document data before deletion
- Allows you to verify you're deleting the right record

### ✅ Dry Run Mode
- Test searches without risk of deletion
- Perfect for diagnostics

### ✅ Validation
- Phone number must be 10-12 digits
- Must be numeric only

## Common Use Cases

### Case 1: Bot Locked Out by Human Handoff

**Symptom:** Bot logs show `Reason: human_handoff` but you can't find the record.

**Solution:**
```bash
python3 scripts/buscar_y_destruir.py --number 573192564288
# Review matches
# Delete the blocking record when prompted
```

### Case 2: Diagnostic Investigation

**Symptom:** Need to see where a phone number exists in the database.

**Solution:**
```bash
python3 scripts/buscar_y_destruir.py --number 573192564288 --dry-run
# Review all matches without deletion
```

### Case 3: Clean Up After Testing

**Symptom:** Test phone numbers scattered across collections.

**Solution:**
```bash
python3 scripts/buscar_y_destruir.py --number 573001234567
# Delete all test records when prompted
```

## Troubleshooting

### Error: "Error initializing Firebase"

**Cause:** Application Default Credentials not configured.

**Fix:**
```bash
gcloud auth application-default login
```

### Error: "Permission denied"

**Cause:** Your account lacks Firestore permissions.

**Fix:** Contact project admin to grant Firestore read/write access.

### Warning: "No matches found"

**Possible Reasons:**
1. Record was already deleted
2. Phone number doesn't exist in database
3. Phone number is stored in a different format (e.g., with country code prefix)

**Next Steps:**
- Try searching with/without country code
- Check if number is stored with special characters (e.g., `+57-319-256-4288`)

## Security Considerations

> [!CAUTION]
> This script can permanently delete production data. Use with care.

**Best Practices:**
1. ✅ Always run with `--dry-run` first
2. ✅ Review full document data before confirming deletion
3. ✅ Keep console output as backup of deleted data
4. ✅ Test on staging environment if available
5. ✅ Only delete records you're certain are causing issues

## Technical Details

### Dependencies
- `firebase-admin>=6.5.0`
- `google-cloud-firestore>=2.19.0`
- Python 3.9+ (3.10+ recommended)

### Performance
- Scans all collections sequentially
- Each collection scanned with 2 strategies (ID + fields)
- Typical execution time: 5-30 seconds depending on database size

### Limitations
- Only scans root-level collections (not subcollections)
- Field queries require fields to be indexed
- Some field queries may fail silently if field doesn't exist (expected behavior)

## Post-Deletion Verification

After deleting a blocking record:

1. **Test the bot:**
   ```bash
   # Send a WhatsApp message from the unblocked number
   # Verify bot responds normally
   ```

2. **Check logs:**
   ```bash
   # Verify no more "human_handoff" errors in Cloud Run logs
   ```

3. **Verify deletion:**
   ```bash
   # Run script again to confirm record is gone
   python3 scripts/buscar_y_destruir.py --number 573192564288 --dry-run
   # Should show "No matches found"
   ```

## Support

If the script doesn't find the blocking record:
1. Check if the phone number format is different in Firestore
2. Verify the record isn't in a subcollection
3. Check Cloud Run logs for the exact field name being checked
4. Consider expanding the `phone_fields` list in the script

---

**Script Location:** `scripts/buscar_y_destruir.py`  
**Created:** 2026-02-06  
**Purpose:** Diagnostic tool for finding and removing hidden Firestore records
