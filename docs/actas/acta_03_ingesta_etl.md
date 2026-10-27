# Acta Semana 3 — Ingesta ETL de catálogos

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario con Inteligencia Artificial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Período reportado** | Semana 3 |
| **Estado** | Implementado y verificado |

---

## 1. Resumen

Se puso en marcha la ingesta de catálogos descrita para la Semana 3. El
administrador puede cargar varios archivos desde el panel de fuentes; el ETL
valida cada archivo de forma independiente, extrae y normaliza sus productos,
los guarda en el catálogo y conserva un historial consultable por usuarios
autenticados. Los errores de un archivo no cancelan el resto del lote.

La implementación respeta las reglas del inventario: el upsert se hace por
código, conserva el stock existente y fija el IVA en 16 %. Los originales se
guardan fuera de los recursos públicos bajo un nombre UUID y su hash SHA-256.

## 2. Alcance entregado

- **Formatos:** PDF con capa de texto, XLSX, DOCX y TXT. No se admiten CSV ni
  XLS. Los documentos tabulares requieren cabeceras reconocibles de código,
  nombre y precio; el TXT también admite el orden posicional documentado.
- **Protecciones:** máximo de 20 archivos por solicitud, 20 MB por archivo,
  20 000 filas por archivo y 300 páginas PDF; se verifica además la estructura
  ZIP de XLSX y DOCX.
- **Persistencia:** metadatos de carga, estado, conteos y detalle; originales
  con UUID y SHA-256 en `UPLOADS_DIR`; inserción o actualización parametrizada
  de productos sin modificar stock ni vectores.
- **API:** `POST /api/v1/inventario/ingesta` limitado a administradores y
  `GET /api/v1/inventario/archivos` disponible para usuarios autenticados.
- **Interfaz:** carga múltiple, resultados por archivo e historial reciente en
  el panel de fuentes.
- **Base de datos y despliegue:** esquema inicial actualizado, migración
  incremental idempotente `3_0` y volumen persistente de originales en Docker.

Los estados persistidos son `pendiente`, `procesando`, `ok`, `parcial` y
`error`. Un archivo rechazado por formato o límites se informa como
`rechazado` y no se almacena como una carga procesada.

## 3. Verificación

| Verificación | Resultado |
|---|---|
| Suite completa | **360 pasaron, 1 omitida**, 165,01 s |
| Prueba de estrés | **1 pasó**: 20 archivos / 5000 productos; se cumplió el límite de 4,25 s |
| Pruebas ETL enfocadas | **27 pasaron**, 4,62 s |
| Migración de desarrollo | No aplicada; la suite aplicó `3_0` a sus bases de prueba desechables |
| Revisión manual en navegador | No realizada en esta ejecución; el flujo quedó cubierto por las pruebas automatizadas de integración |

La suite reportó un aviso de obsolescencia de `starlette.testclient` con
`httpx`; no afectó los resultados.

## 4. Aplicación en una instalación existente

La migración `3_0` se puede aplicar sin recrear volúmenes ni borrar datos:

```powershell
venv\Scripts\python.exe scripts\aplicar_migracion.py 3_0
```

En una instalación nueva, `init.sql` incluye el esquema de ingesta. Los
originales deben permanecer en el volumen persistente configurado como
`UPLOADS_DIR`; nunca deben exponerse desde `app/static`.

## 5. Alcance pendiente

La ingesta registra productos para las etapas siguientes del proyecto, pero no
implementa embeddings, búsqueda vectorial ni respuestas RAG definitivas. Esas
funcionalidades corresponden a semanas posteriores.
