-- Migracion 4.0 - Semana 4: modelo multilingual-e5-small (384 dimensiones).
--
-- Nunca trunca ni convierte vectores existentes. Si encuentra embeddings,
-- aborta para evitar mezclar modelos; deben respaldarse y regenerarse antes.

DO $$
DECLARE
    dimension_actual INTEGER;
BEGIN
    SELECT substring(format_type(a.atttypid, a.atttypmod) FROM
                     '^vector[(]([0-9]+)[)]$')::INTEGER
      INTO dimension_actual
      FROM pg_attribute a
     WHERE a.attrelid = 'productos'::regclass
       AND a.attname = 'descripcion_vectorial'
       AND NOT a.attisdropped;

    IF dimension_actual IS NULL THEN
        RAISE EXCEPTION
            'No se pudo determinar la dimension actual de productos.descripcion_vectorial';
    END IF;

    IF dimension_actual = 384 THEN
        NULL;
    ELSIF dimension_actual = 1536 THEN
        IF EXISTS (
            SELECT 1
              FROM productos
             WHERE descripcion_vectorial IS NOT NULL
        ) THEN
            RAISE EXCEPTION
                'Hay embeddings existentes de 1536 dimensiones; respaldelos y regenere todos antes de migrar';
        END IF;

        DROP INDEX IF EXISTS idx_productos_descripcion_vectorial;
        ALTER TABLE productos
            ALTER COLUMN descripcion_vectorial TYPE vector(384)
            USING NULL::vector(384);
    ELSE
        RAISE EXCEPTION
            'Dimension vectorial no compatible: %. Se esperaba 1536 o 384',
            dimension_actual;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_productos_descripcion_vectorial
    ON productos USING hnsw (descripcion_vectorial vector_cosine_ops);
