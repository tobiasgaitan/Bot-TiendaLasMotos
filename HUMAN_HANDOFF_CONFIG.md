# Human Handoff Feature - Configuration Guide

## Overview
The Human Handoff feature allows the chatbot to escalate conversations to human agents when users request assistance or when the AI determines a query is too complex.

## Required Environment Variables

### Admin Contact Information
These variables define where handoff notifications will be sent:

```bash
# Admin WhatsApp number (with country code, no + or spaces)
ADMIN_WHATSAPP=573001234567

# Admin email address
ADMIN_EMAIL=admin@tiendalasmotos.com
```

### Email Configuration (Optional)
If you want to receive email notifications, configure these SMTP settings:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

**Note:** If SMTP credentials are not configured, email notifications will be skipped gracefully (logged as warnings), but WhatsApp notifications will still work.

## Setup Instructions

### 1. Local Development
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set your admin contact information:
   ```bash
   ADMIN_WHATSAPP=57300XXXXXXX  # Your actual admin WhatsApp
   ADMIN_EMAIL=admin@yourdomain.com
   ```

3. (Optional) Configure SMTP for email alerts:
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your.email@gmail.com
   SMTP_PASSWORD=your_app_specific_password
   ```

### 2. Cloud Run Deployment
Set environment variables in Cloud Run:

```bash
gcloud run services update bot-tiendalasmotos \
  --update-env-vars ADMIN_WHATSAPP=573001234567 \
  --update-env-vars ADMIN_EMAIL=admin@tiendalasmotos.com \
  --region us-central1
```

For email notifications (optional):
```bash
gcloud run services update bot-tiendalasmotos \
  --update-env-vars SMTP_HOST=smtp.gmail.com \
  --update-env-vars SMTP_PORT=587 \
  --update-env-vars SMTP_USER=your.email@gmail.com \
  --update-secrets SMTP_PASSWORD=smtp-password:latest \
  --region us-central1
```

## How It Works

### Trigger Conditions
The bot will trigger a human handoff when:
1. **User explicitly requests**: Keywords like "humano", "persona", "asesor", "compañero"
2. **Complex queries**: AI determines it cannot handle the request
3. **Angry sentiment**: User shows frustration (existing feature, now integrated)

### Handoff Process
1. AI calls `trigger_human_handoff` function
2. Session is marked as `paused: true` in Firestore
3. Notifications sent to admin via:
   - WhatsApp message to `ADMIN_WHATSAPP`
   - Email to `ADMIN_EMAIL` (if configured)
4. User receives exact message: "Te pondré en contacto con un compañero con más conocimiento del tema."
5. Bot stops responding to that user (kill switch active)

### Kill Switch
Once a session is paused:
- All incoming messages from that user are silently ignored
- No responses are sent (prevents bot from interfering with human agent)
- Session remains paused until manually resumed in Firestore

### Resuming Sessions
To resume a paused session, update Firestore:
```javascript
// In Firestore console or admin panel
db.collection('mensajeria')
  .doc('whatsapp')
  .collection('sesiones')
  .doc('{phone_number}')
  .update({ paused: false, status: 'IDLE' })
```

## Testing

### Test Handoff Trigger
Send a WhatsApp message:
```
Quiero hablar con un humano
```

Expected results:
- ✅ Bot responds: "Te pondré en contacto con un compañero con más conocimiento del tema."
- ✅ Session marked as paused in Firestore
- ✅ Admin receives WhatsApp notification
- ✅ Admin receives email (if SMTP configured)

### Test Kill Switch
After triggering handoff, send another message:
```
Hola, sigues ahí?
```

Expected result:
- ✅ Bot does not respond (message silently ignored)
- ✅ Logs show: "Session paused for {phone} | Reason: human_handoff | Message ignored"

## Troubleshooting

### Email Notifications Not Working
- Check SMTP credentials are correct
- For Gmail: Use App Password, not regular password
- Verify `ADMIN_EMAIL` is set
- Check logs for SMTP errors

### WhatsApp Notifications Not Working
- Verify `ADMIN_WHATSAPP` format (country code + number, no spaces)
- Check `WHATSAPP_TOKEN` and `PHONE_NUMBER_ID` are configured
- Ensure admin number is registered in WhatsApp Business

### Bot Still Responding After Handoff
- Check Firestore session document has `paused: true`
- Verify logs show kill switch activation
- Ensure latest code is deployed

## Security Notes
- All credentials stored in environment variables (never hardcoded)
- SMTP password should use Secret Manager in production
- Notifications fail gracefully (don't crash the bot)
- Kill switch uses fail-closed approach (defaults to paused if uncertain)
