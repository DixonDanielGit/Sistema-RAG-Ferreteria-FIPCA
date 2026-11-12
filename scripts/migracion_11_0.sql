-- Migracion 11.0 - Retiro de la columna heredada de un diseno anterior.
--
-- La columna archivos_subidos.contenido_markdown pertenecia al diseno anterior
-- y la aplicacion actual no la usa. Esta migracion la retira de forma
-- idempotente; si la instalacion nunca aplico la 10_0, no hay nada que hacer.
--
-- No toca productos, ofertas ni datos de inventario y puede repetirse sin
-- efecto (idempotente).
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 11_0

ALTER TABLE archivos_subidos
    DROP COLUMN IF EXISTS contenido_markdown;
