# Reglas de Negocio - Tienda Las Motos

## Gobernanza de Datos

**SSOT Documental:** Este documento (`docs/BUSINESS_RULES.md`) es la guía de estilo y de reglas de negocio para humanos (equipo comercial, auditores y mantenedores del agente). Describe el comportamiento esperado del agente, pero **no lo ejecuta**.

**SSOT de Ejecución:** El comportamiento en runtime del Cerebro IA (`ai_brain.py`) y del Juez (`judge_service.py`) se rige exclusivamente por:
1. **Catálogo Firestore — campo `searchBy`:** define las equivalencias de competencia vigentes (leído por `CatalogService` y `ai_brain._load_searchby_aliases`; validado por `JudgeService`).
2. **Prompt `juan_pablo_personality`** (Firestore `configuracion/juan_pablo_personality.system_instruction`, sincronizado únicamente vía `scripts/sync_full_prompt.py`): define la voz en primera persona singular, el tono y los scripts del asesor.

**Regla de Precedencia:** En caso de divergencia entre este documento y el SSOT de Ejecución, **prevalece siempre el SSOT de Ejecución**. Toda corrección de equivalencias de competencia o de voz debe aplicarse primero en el catálogo/prompt y después reflejarse aquí. Editar únicamente este documento **no produce ningún efecto en runtime**.

## Protocolo de Competencia (v1.1)
**Estado:** Activo (Fase Beta)
**Fecha:** 2026-07-27

### Objetivo
Permitir que la IA actúe como un asesor comercial proactivo cuando los usuarios pregunten por modelos de marcas competidoras que no forman parte del catálogo oficial de Auteco/Tienda Las Motos (TVS, Victory).

### Definición de "Venta por Equivalencia"
Cuando un usuario menciona un modelo de competencia, el sistema no debe rechazar la consulta. En su lugar, debe buscar un equivalente en el catálogo interno utilizando los metadatos de búsqueda (`searchBy`).

### Criterios de Calidad (Actualización C4)
*   **C4 (Catalog Lock - Flexibilizado):** El bot tiene prohibido inventar especificaciones de productos internos, pero tiene permiso explícito para mencionar modelos externos (ej. Boxer, NKD) con el fin de posicionar una alternativa interna.
*   **Validación del Juez:** El `JudgeService` marcará como **APPROVED** las respuestas que mencionen marcas de competencia siempre y cuando el producto ofrecido contenga el término de competencia en sus etiquetas de búsqueda.

### Tabla de Equivalencias Sugeridas (Metadata-Driven)
> ⚠️ Tabla **ilustrativa**: la equivalencia vigente en runtime la define el campo `searchBy` del catálogo en Firestore (SSOT de Ejecución), no esta tabla.
| Modelo Competencia | Equivalente Tienda Las Motos | Ventaja Comercial |
| :--- | :--- | :--- |
| **NKD 125** | Victory Bomber 125 | Mejor diseño, tecnología Euro 3, respaldo Auteco. |
| **Boxer CT 100** | TVS Sport 100 | La moto más económica en consumo, tecnología Duralife. |
| **Pulsar NS 200** | TVS Apache RTR 200 4V | Tecnología de carreras, embrague antirebote, mejor torque. |

### Script Comercial Recomendado
> "No manejo la **[Moto_Competencia]** directamente, pero tengo la **[Moto_Nuestra]** que es su equivalente ideal y superior por **[Ventaja]**. Aquí te comparto los detalles: ..."

---
*SSOT Documental: guía de estilo y reglas de negocio para humanos. El SSOT de Ejecución —campo `searchBy` del catálogo en Firestore y prompt `juan_pablo_personality`— tiene precedencia absoluta ante cualquier divergencia (ver "Gobernanza de Datos").*
