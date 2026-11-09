-- Migracion 10.0 - Conversion de catalogos a Markdown con MarkItDown (RF-02.4).
--
-- El ETL convierte los archivos subidos (PDF, XLSX, DOCX o TXT) a Markdown con
-- Microsoft MarkItDown, lee directamente las fuentes .md y guarda ese texto
-- junto al registro del archivo original:
--
--   * archivos_subidos.contenido_markdown -> Markdown fuente o convertido
--
-- Para PDF, XLSX, DOCX y TXT, un fallo al convertir no detiene los lectores de
-- filas. Un archivo .md usa ese texto como insumo y requiere que OpenRouter
-- pueda transformarlo a productos estructurados antes de cargarlos.
-- No toca productos, ofertas ni datos de inventario y puede repetirse sin
-- efecto (idempotente).
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 10_0

ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS contenido_markdown TEXT;

COMMENT ON COLUMN archivos_subidos.contenido_markdown IS
    'Markdown original o convertido con Microsoft MarkItDown (RF-02.4).';
