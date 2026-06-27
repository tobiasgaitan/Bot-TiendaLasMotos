import http from 'k6/http';
import crypto from 'k6/crypto';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('tasa_errores_webhook');
const secret = __ENV.WHATSAPP_APP_SECRET || '***REMOVED***';

export const options = {
  vus: 100,
  duration: '30s',
  thresholds: {
    tasa_errores_webhook: ['rate<0.01'],             // Máximo 1% de errores de red
    http_req_duration: ['p(95)<15000', 'p(99)<20000'], // El 95% en < 15s, el 99% en < 20s (flujo síncrono LLM + Firestore)
  },
};

export default function () {
  const url = 'http://localhost:8000/webhook';
  const payload = JSON.stringify({
    object: 'whatsapp_business_account',
    entry: [{
      id: '123456',
      changes: [{
        value: {
          messaging_product: 'whatsapp',
          metadata: { display_phone_number: '1234567890', phone_number_id: '1234567890' },
          messages: [{
            from: `57300${Math.floor(1000000 + Math.random() * 9000000)}`,
            id: `k6_${Math.random().toString(36).substring(7)}`,
            timestamp: Math.floor(Date.now() / 1000).toString(),
            text: { body: 'Precio de la TVS' },
            type: 'text'
          }]
        },
        field: 'messages'
      }]
    }]
  });

  const signature = crypto.hmac('sha256', secret, payload, 'hex');

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Hub-Signature-256': `sha256=${signature}`
    },
  };

  const res = http.post(url, payload, params);
  
  const result = check(res, {
    'status es 200': (r) => r.status === 200,
  });

  if (!result) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }

  sleep(0.1);
}
