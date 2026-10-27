-- =====================================================================
-- Migracion 2.5 - Adenda 1: recuperacion de contrasena
--
-- Se aplica sobre una base YA existente (ferreteria_usuarios) para no tener
-- que borrar el volumen con `docker compose down -v`. Es idempotente: puede
-- ejecutarse varias veces sin efectos secundarios.
--
-- Uso:
--   docker exec -i postgres_ferreteria \
--     psql -U postgres -d ferreteria_usuarios -v ON_ERROR_STOP=1 \
--     < scripts/migracion_2_5.sql
--
-- init.sql ya incluye esta misma tabla para instalaciones nuevas.
-- =====================================================================

CREATE TABLE IF NOT EXISTS tokens_recuperacion (
    id SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_en TIMESTAMPTZ NOT NULL,
    usado_en TIMESTAMPTZ,

    CONSTRAINT fk_tokens_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        ON DELETE CASCADE,
    CONSTRAINT chk_tokens_vigencia
        CHECK (expira_en > creado_en)
);

CREATE INDEX IF NOT EXISTS idx_tokens_usuario ON tokens_recuperacion (id_usuario);
CREATE INDEX IF NOT EXISTS idx_tokens_expira ON tokens_recuperacion (expira_en);

-- Permisos: el rol de la API consulta, crea y marca como usado.
-- Sin DELETE: los tokens se invalidan con UPDATE para conservar el rastro.
GRANT SELECT, INSERT, UPDATE ON tokens_recuperacion TO app_ferreteria;
GRANT USAGE, SELECT ON SEQUENCE tokens_recuperacion_id_seq TO app_ferreteria;

COMMENT ON TABLE tokens_recuperacion IS
    'Enlaces de recuperacion de contrasena: token hasheado, un solo uso y caducidad';
