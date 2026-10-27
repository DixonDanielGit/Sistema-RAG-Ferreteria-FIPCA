-- Migracion 3.0 - Semana 3: historial y almacenamiento de ingestas ETL.
--
-- Se aplica sobre ferreteria_rag sin borrar el volumen ni los catalogos
-- existentes. Los registros previos quedan marcados como completados.

ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS ruta TEXT,
    ADD COLUMN IF NOT EXISTS hash_sha256 CHAR(64),
    ADD COLUMN IF NOT EXISTS tamano_bytes BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'ok',
    ADD COLUMN IF NOT EXISTS filas_ok INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS filas_error INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS detalle TEXT,
    ADD COLUMN IF NOT EXISTS id_usuario INT,
    ADD COLUMN IF NOT EXISTS terminado_en TIMESTAMPTZ;

ALTER TABLE archivos_subidos
    ALTER COLUMN estado SET DEFAULT 'pendiente';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'chk_archivos_estado'
           AND conrelid = 'archivos_subidos'::regclass
    ) THEN
        ALTER TABLE archivos_subidos
            ADD CONSTRAINT chk_archivos_estado
            CHECK (estado IN ('pendiente', 'procesando', 'ok', 'parcial', 'error'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'chk_archivos_tamano'
           AND conrelid = 'archivos_subidos'::regclass
    ) THEN
        ALTER TABLE archivos_subidos
            ADD CONSTRAINT chk_archivos_tamano CHECK (tamano_bytes >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'chk_archivos_filas_ok'
           AND conrelid = 'archivos_subidos'::regclass
    ) THEN
        ALTER TABLE archivos_subidos
            ADD CONSTRAINT chk_archivos_filas_ok CHECK (filas_ok >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'chk_archivos_filas_error'
           AND conrelid = 'archivos_subidos'::regclass
    ) THEN
        ALTER TABLE archivos_subidos
            ADD CONSTRAINT chk_archivos_filas_error CHECK (filas_error >= 0);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_archivos_hash ON archivos_subidos (hash_sha256);
CREATE INDEX IF NOT EXISTS idx_archivos_fecha
    ON archivos_subidos (fecha_de_subida DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON archivos_subidos TO app_ferreteria;
GRANT USAGE, SELECT ON SEQUENCE archivos_subidos_id_archivo_seq TO app_ferreteria;
