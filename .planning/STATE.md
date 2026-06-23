Versión: v10.7.1
Posición: Integración de la asincronización de AgenticOrchestrator y reintento conversacional (BOT-QA-LOOP-107).
Coherence Score: 1.000 (Certificado de No-Regresión)

### Decisiones Clave
- Asincronización de `create_sandbox` y `destroy_sandbox` usando `asyncio.create_subprocess_exec` para no bloquear el Event Loop.
- Implementación de bucle de reintento de validación post-generación en `pensar_respuesta` de CerebroIA usando el validador local a `temperature=0.1`.
- Ajuste de los tests de integración mock para alinearse con los guardrails conversacionales y prevenir falsas alarmas de reintento.
