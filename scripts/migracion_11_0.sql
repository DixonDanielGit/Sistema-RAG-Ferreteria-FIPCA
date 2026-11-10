-- Migracion 11.0 - Markdown de catalogos en disco (RF-02.4).
--
-- El Markdown derivado del catalogo ya no se guarda en la base: es informacion
-- derivada del archivo original y se conserva en:
--
--   UPLOADS_DIR/markdown/<id_archivo>.md
--
-- Al eliminar un catalogo se borran, en este orden, su registro y productos en
-- la base y despues el original y su Markdown del disco. Si el borrado fisico
-- falla, queda registrado en el log para que la limpieza pueda reintentarse.
--
-- No toca productos, ofertas ni datos de inventario y puede repetirse sin
-- efecto (idempotente).
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 11_0

ALTER TABLE archivos_subidos
    DROP COLUMN IF EXISTS contenido_markdown;
