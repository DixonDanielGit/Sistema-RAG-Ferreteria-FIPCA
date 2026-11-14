-- Migracion 13.0 - Token de confirmacion para previsualizacion diferida.
--
-- Agrega una columna UUID unica a archivos_subidos para identificar de forma
-- segura las previsualizaciones pendientes. La ingesta posterior usa este
-- token en vez de reenviar y reextraer el archivo.
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 13_0

-- Columna: token_confirmacion
-- Se genera automaticamente con gen_random_uuid() para filas nuevas.
-- Las filas existentes quedan en NULL (no necesitan token).
ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS token_confirmacion UUID UNIQUE
        DEFAULT gen_random_uuid();

COMMENT ON COLUMN archivos_subidos.token_confirmacion IS
    'Token UUID de un solo uso para confirmar la ingesta diferida. Se asigna en la previsualizacion y se consume al ingestar o cancelar.';

-- Extiende el CHECK de estado para incluir 'rechazado' (cancelacion del usuario
-- o expiracion automatica del token).
ALTER TABLE archivos_subidos
    DROP CONSTRAINT IF EXISTS chk_archivos_estado,
    ADD CONSTRAINT chk_archivos_estado
        CHECK (estado IN ('pendiente', 'procesando', 'ok', 'parcial', 'error', 'rechazado'));

-- Indice parcial para buscar rapidamente tokens pendientes
CREATE INDEX IF NOT EXISTS idx_archivos_token_pendiente
    ON archivos_subidos (token_confirmacion)
    WHERE estado = 'pendiente' AND token_confirmacion IS NOT NULL;