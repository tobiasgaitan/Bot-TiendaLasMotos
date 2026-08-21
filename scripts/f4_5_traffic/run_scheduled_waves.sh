#!/bin/zsh
# Orquestador de oleadas 2, 3 y 4 de F4.5 (~6h de separación, orden alternado).
# Lanzar con: nohup scripts/f4_5_traffic/run_scheduled_waves.sh &

cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos || exit 1

# Carga credenciales desde la configuración del servicio Cloud Run.
eval $(gcloud run services describe bot-tiendalasmotos-beta \
  --project=tiendalasmotos \
  --region=us-central1 \
  --format="json(spec.template.spec.containers[0].env)" \
  | .venv/bin/python -c "
import sys, json
data = json.load(sys.stdin)
env = data.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [{}])[0].get('env', [])
for e in env:
    name = e.get('name', '')
    if name.startswith('LANGFUSE') or name == 'WEBHOOK_VERIFY_TOKEN':
        print(f\"export {name}=\\\"{e.get('value', '')}\\\"\")
")

export GOOGLE_CLOUD_PROJECT=tiendalasmotos

LOG="scripts/f4_5_traffic/results/scheduled_waves.log"
mkdir -p scripts/f4_5_traffic/results

run_wave() {
  local wave=$1
  local run_id=$2
  echo "=== $(date): Iniciando oleada ${wave} (${run_id}) ===" >> "$LOG"
  .venv/bin/python scripts/f4_5_traffic/run_wave.py --wave "$wave" --run-id "$run_id" --concurrency 6 >> "$LOG" 2>&1
}

analyze_wave() {
  local run_id=$1
  echo "=== $(date): Analizando ${run_id} ===" >> "$LOG"
  .venv/bin/python scripts/f4_5_traffic/analyze_wave.py "$run_id" >> "$LOG" 2>&1
}

{
  echo "=== $(date): Orquestador de oleadas 2-4 iniciado ==="

  # ~6h hasta la oleada 2
  sleep 21600
  run_wave 2 wave2-20260821-0715
  analyze_wave wave2-20260821-0715

  # ~6h hasta la oleada 3
  sleep 21600
  run_wave 3 wave3-20260821-1315
  analyze_wave wave3-20260821-1315

  # ~6h hasta la oleada 4
  sleep 21600
  run_wave 4 wave4-20260821-1915
  analyze_wave wave4-20260821-1915

  echo "=== $(date): Oleadas 2-4 completadas ==="
} >> "$LOG" 2>&1
