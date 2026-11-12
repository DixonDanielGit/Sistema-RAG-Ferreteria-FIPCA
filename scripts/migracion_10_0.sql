-- Migracion 10.0 - Columna heredada de un diseno anterior (RF-02.4).
--
-- Conserva la columna archivos_subidos.contenido_markdown para instalaciones
-- que ya la tuvieron. La aplicacion actual no la lee ni la escribe: la ingesta
-- es local y determinista, y la migracion 11_0 retira la columna.
--
-- No toca productos, ofertas ni datos de inventario y puede repetirse sin
-- efecto (idempotente).
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 10_0

ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS contenido_markdown TEXT;

COMMENT ON COLUMN archivos_subidos.contenido_markdown IS
    'Columna heredada de un diseno anterior; la aplicacion actual no la usa.';
