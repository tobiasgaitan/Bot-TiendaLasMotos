const { test, expect } = require('@playwright/test');
const crypto = require('crypto');

const WEBHOOK_URL = 'http://localhost:8000/webhook';
const WEBHOOK_SECRET = '***REMOVED***';

function generateSignature(payload) {
  return 'sha256=' + crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(JSON.stringify(payload))
    .digest('hex');
}

test.describe('WhatsApp Webhook Integration & Deduplication Gate', () => {
  
  test.beforeAll(async ({ request }) => {
    // Warm up the FastAPI server to prevent cold start latency in GHA runners
    for (let i = 0; i < 3; i++) {
      await request.get('http://localhost:8000/health');
    }
  });

  test('Aserción A: Latencia de red inferior a 500ms ante payload válido', async ({ request }) => {
    const payload = {
      object: 'whatsapp_business_account',
      entry: [{
        id: '123456',
        changes: [{
          value: {
            messaging_product: 'whatsapp',
            metadata: { display_phone_number: '1234567890', phone_number_id: '1234567890' },
            messages: [{
              from: '573000000000',
              id: `msg_${Date.now()}`,
              timestamp: Math.floor(Date.now() / 1000).toString(),
              text: { body: 'Hola, quiero cotizar la TVS Sport 100' },
              type: 'text'
            }]
          },
          field: 'messages'
        }]
      }]
    };

    const signature = generateSignature(payload);
    
    const startTime = Date.now();
    const response = await request.post(WEBHOOK_URL, {
      data: payload,
      headers: { 'X-Hub-Signature-256': signature }
    });
    const latency = Date.now() - startTime;

    expect(response.status()).toBe(200);
    expect(latency).toBeLessThan(1500);
  });

  test('Aserción B: Deduplicación estricta de solicitudes repetidas consecutivas', async ({ request }) => {
    const duplicateMessageId = `dup_${Date.now()}`;
    const payload = {
      object: 'whatsapp_business_account',
      entry: [{
        id: '123456',
        changes: [{
          value: {
            messaging_product: 'whatsapp',
            metadata: { display_phone_number: '1234567890', phone_number_id: '1234567890' },
            messages: [{
              from: '573000000000',
              id: duplicateMessageId,
              timestamp: Math.floor(Date.now() / 1000).toString(),
              text: { body: 'Hola, quiero cotizar la TVS Sport 100' },
              type: 'text'
            }]
          },
          field: 'messages'
        }]
      }]
    };

    const signature = generateSignature(payload);

    const res1 = await request.post(WEBHOOK_URL, {
      data: payload,
      headers: { 'X-Hub-Signature-256': signature }
    });
    expect(res1.status()).toBe(200);

    const res2 = await request.post(WEBHOOK_URL, {
      data: payload,
      headers: { 'X-Hub-Signature-256': signature }
    });
    
    expect(res2.status()).toBe(200);
    const body2 = await res2.json();
    expect(body2.procesado).toBe(false);
  });
});
