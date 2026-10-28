-- =====================================================================
-- Migracion 5.0 - Perfil y gestion de usuarios
--
-- Agrega almacenamiento de imagen al perfil sin recrear la base ni perder
-- cuentas existentes. Puede ejecutarse varias veces.
-- =====================================================================

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS imagen_perfil BYTEA;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'chk_usuarios_imagen_perfil_tamano'
           AND conrelid = 'usuarios'::regclass
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT chk_usuarios_imagen_perfil_tamano
            CHECK (imagen_perfil IS NULL OR octet_length(imagen_perfil) <= 2097152);
    END IF;
END
$$;

COMMENT ON COLUMN usuarios.imagen_perfil IS
    'Imagen de perfil JPEG, PNG o WebP validada por la API; maximo 2 MiB';

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_usuario_lower
    ON usuarios (LOWER(usuario));
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_correo_lower
    ON usuarios (LOWER(correo));
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_cedula_lower
    ON usuarios (LOWER(cedula));
