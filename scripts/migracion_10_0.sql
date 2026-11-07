-- Migracion 10.0 - Conversion de catalogos a Markdown con MarkItDown (RF-02.4).
--
-- El ETL convierte cada archivo subido (PDF, XLSX, DOCX o TXT) a Markdown con
-- Microsoft MarkItDown, el paso unico de lectura y normalizacion del documento,
-- y guarda ese texto junto al registro del archivo original:
--
--   * archivos_subidos.contenido_markdown -> Markdown producido por MarkItDown
--
-- El texto queda vacio (NULL) solo si la conversion no pudo ejecutarse; el
-- catalogo igual se procesa con los lectores de filas (tolerancia RF-02.3).
-- No toca productos, ofertas ni datos de inventario y puede repetirse sin
-- efecto (idempotente).
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 10_0

ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS contenido_markdown TEXT;

COMMENT ON COLUMN archivos_subidos.contenido_markdown IS
    'Contenido del catalogo convertido a Markdown por Microsoft MarkItDown (RF-02.4).';
