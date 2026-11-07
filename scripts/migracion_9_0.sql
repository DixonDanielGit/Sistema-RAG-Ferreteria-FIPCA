-- Migracion 9.0 - Buscador comercial: Full-Text Search nativo de PostgreSQL.
--
-- Agrega a productos la columna texto_busqueda, calculada sola (GENERATED
-- ALWAYS) con el diccionario espanol sobre codigo, nombre, marca, descripcion
-- y presentacion, mas los indices GIN que permiten responder en milisegundos
-- sin recorrer el catalogo entero:
--
--   * idx_productos_texto_busqueda   -> tsvector (@@ / plainto_tsquery)
--   * idx_productos_codigo_trgm      -> ILIKE parcial sobre el codigo
--   * idx_proveedores_nombre_trgm    -> ILIKE parcial sobre el proveedor
--   * idx_categoria_nombre_trgm      -> ILIKE parcial sobre la categoria
--
-- No toca vectores, embeddings ni datos de inventario y puede repetirse sin
-- efecto (idempotente).
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 9_0

ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS texto_busqueda tsvector
    GENERATED ALWAYS AS (
        to_tsvector(
            'spanish'::regconfig,
            coalesce(nombre, '') || ' ' ||
            coalesce(codigo, '') || ' ' ||
            coalesce(codigo_interno, '') || ' ' ||
            coalesce(marca, '') || ' ' ||
            coalesce(descripcion, '') || ' ' ||
            coalesce(presentacion, '') || ' ' ||
            coalesce(unidad_medida, '') || ' ' ||
            coalesce(ubicacion, '')
        )
    ) STORED;

COMMENT ON COLUMN productos.texto_busqueda IS
    'Vector de texto en espanol para el Buscador Comercial; se recalcula automaticamente.';

CREATE INDEX IF NOT EXISTS idx_productos_texto_busqueda
    ON productos USING gin (texto_busqueda);

CREATE INDEX IF NOT EXISTS idx_productos_codigo_trgm
    ON productos USING gin (codigo gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_proveedores_nombre_trgm
    ON proveedores USING gin (nombre gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_categoria_nombre_trgm
    ON categoria USING gin (nombre gin_trgm_ops);
