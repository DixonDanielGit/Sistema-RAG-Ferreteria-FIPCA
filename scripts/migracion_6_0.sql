-- =====================================================================
-- Migracion 6.0 - Roles configurables y permisos por capacidades
--
-- Amplia ferreteria_usuarios sin eliminar ni recrear cuentas. Idempotente.
-- =====================================================================

ALTER TABLE rol
    ADD COLUMN IF NOT EXISTS protegido BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE rol
   SET protegido = TRUE,
       descripcion = COALESCE(
           NULLIF(descripcion, ''),
           'Acceso total a las funciones administrativas del sistema'
       )
 WHERE LOWER(nombre) = 'admin';

CREATE UNIQUE INDEX IF NOT EXISTS uq_rol_nombre_lower
    ON rol (LOWER(nombre));

CREATE TABLE IF NOT EXISTS permiso (
    id_permiso SERIAL PRIMARY KEY,
    clave VARCHAR(80) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    orden SMALLINT NOT NULL DEFAULT 0
);

INSERT INTO permiso (clave, nombre, descripcion, orden) VALUES
    ('usuarios:gestionar', 'Gestionar usuarios', 'Consultar y administrar cuentas del sistema.', 10),
    ('catalogos:ingestar', 'Cargar catalogos', 'Cargar catalogos de productos y consultar su procesamiento.', 20),
    ('catalogos:eliminar', 'Eliminar catalogos', 'Eliminar catalogos y los productos que contienen.', 30),
    ('configuracion:diagnostico', 'Consultar diagnostico', 'Consultar estado de bases de datos y limites tecnicos.', 40)
ON CONFLICT (clave) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    orden = EXCLUDED.orden;

CREATE TABLE IF NOT EXISTS rol_permiso (
    id_rol INT NOT NULL,
    id_permiso INT NOT NULL,
    PRIMARY KEY (id_rol, id_permiso),
    CONSTRAINT fk_rol_permiso_rol
        FOREIGN KEY (id_rol) REFERENCES rol(id_rol) ON DELETE CASCADE,
    CONSTRAINT fk_rol_permiso_permiso
        FOREIGN KEY (id_permiso) REFERENCES permiso(id_permiso) ON DELETE RESTRICT
);

-- Completa tambien instalaciones donde 6_0 se ejecuto antes de incluir la semilla.
INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
  FROM rol r
 CROSS JOIN permiso p
 WHERE LOWER(r.nombre) = 'admin'
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

GRANT SELECT ON permiso TO app_ferreteria;
GRANT SELECT, INSERT, UPDATE, DELETE ON rol TO app_ferreteria;
GRANT SELECT, INSERT, DELETE ON rol_permiso TO app_ferreteria;
GRANT USAGE, SELECT ON SEQUENCE rol_id_rol_seq TO app_ferreteria;
GRANT USAGE, SELECT ON SEQUENCE permiso_id_permiso_seq TO app_ferreteria;
