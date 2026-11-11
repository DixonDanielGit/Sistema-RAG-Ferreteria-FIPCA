-- Migracion 12.0 - Observaciones comerciales por catalogo y producto.
--
-- La observacion del catalogo es compartida por todos los productos asociados
-- a ese archivo. La observacion de producto es independiente.
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 12_0

ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS observacion_comercial TEXT;

ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS observacion_comercial TEXT;

COMMENT ON COLUMN archivos_subidos.observacion_comercial IS
    'Nota comercial compartida por los productos asociados al catalogo.';

COMMENT ON COLUMN productos.observacion_comercial IS
    'Nota comercial particular del producto.';
