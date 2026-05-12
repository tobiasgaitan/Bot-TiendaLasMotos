# Reglas de Negocio - Tienda Las Motos

## Protocolo de Competencia (v1.0)
**Estado:** Activo (Fase Beta)
**Fecha:** 2026-05-12

### Objetivo
Permitir que la IA actúe como un asesor comercial proactivo cuando los usuarios pregunten por modelos de marcas competidoras que no forman parte del catálogo oficial de Auteco/Tienda Las Motos (TVS, Victory).

### Definición de "Venta por Equivalencia"
Cuando un usuario menciona un modelo de competencia, el sistema no debe rechazar la consulta. En su lugar, debe buscar un equivalente en el catálogo interno utilizando los metadatos de búsqueda (`search_by`).

### Criterios de Calidad (Actualización C4)
*   **C4 (Catalog Lock - Flexibilizado):** El bot tiene prohibido inventar especificaciones de productos internos, pero tiene permiso explícito para mencionar modelos externos (ej. Boxer, NKD) con el fin de posicionar una alternativa interna.
*   **Validación del Juez:** El `JudgeService` marcará como **APPROVED** las respuestas que mencionen marcas de competencia siempre y cuando el producto ofrecido contenga el término de competencia en sus etiquetas de búsqueda.

### Tabla de Equivalencias Sugeridas (Metadata-Driven)
| Modelo Competencia | Equivalente Tienda Las Motos | Ventaja Comercial |
| :--- | :--- | :--- |
| **NKD 125** | Victory Bomber 125 | Mejor diseño, tecnología Euro 3, respaldo Auteco. |
| **Boxer CT 100** | TVS Sport 100 | La moto más económica en consumo, tecnología Duralife. |
| **Pulsar NS 200** | TVS Apache RTR 200 4V | Tecnología de carreras, embrague antirebote, mejor torque. |

### Script Comercial Recomendado
> "No manejamos la **[Moto_Competencia]** directamente, pero tengo la **[Moto_Nuestra]** que es su equivalente ideal y superior por **[Ventaja]**. Aquí te comparto los detalles: ..."

---
*Este documento es la Fuente de Verdad (SSOT) para la lógica de auditoría del Juez y el comportamiento del Cerebro IA.*
