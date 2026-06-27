---
task: 075
name: Hotfix CI k6 GPG Key Installation
description: Reemplazar lógica GPG keyserver con pipeline atómico de descarga directa para k6
---

# Quick Task 075: Hotfix CI k6 GPG Key Installation

## Objective
Eliminar los comandos gpg que utilizan `--keyserver` y lógica de fallback bash en el paso 'Install Grafana k6' de `qa-pipeline.yml`. Reemplazar con pipeline atómico seguro de descarga directa vía curl.

## Root Cause
- `curl: 23` → Error de permisos de escritura al intentar dearmor dentro del fallback.
- Keyserver HKP colapsa intermitentemente en runners efímeros de GitHub Actions.
- La lógica de fallback con `||` introduce complejidad innecesaria y puntos de fallo adicionales.

## Tasks

<task type="auto">
  <name>Reemplazar paso Install Grafana k6 con pipeline atómico</name>
  <files>.github/workflows/qa-pipeline.yml</files>
  <action>
    Reemplazar líneas 73-83 del paso 'Install Grafana k6' con:
    ```yaml
    - name: Install Grafana k6
      run: |
        curl -sL https://dl.k6.io/key.gpg | sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --import
        echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update && sudo apt-get install -y k6
    ```
  </action>
  <verify>cat .github/workflows/qa-pipeline.yml | grep -A5 "Install Grafana k6"</verify>
  <done>El paso usa exclusivamente curl + gpg --import sin keyserver ni fallback bash</done>
</task>

---
*Created: 2026-06-27*
