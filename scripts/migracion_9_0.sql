-- =====================================================================
-- Migracion 9.0 - Capacidad de consulta de la bitacora (RF-05.2)
--
-- Agrega la capacidad bitacora:consultar para que el visor de auditoria
-- pueda asignarse a roles desde Configuracion. El rol admin la recibe por
-- defecto. Idempotente: puede ejecutarse mas de una vez sin duplicar filas.
-- =====================================================================

INSERT INTO permiso (clave, nombre, descripcion, orden) VALUES
    ('bitacora:consultar', 'Consultar bitacora', 'Consultar el historial de auditoria del sistema.', 50)
ON CONFLICT (clave) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    orden = EXCLUDED.orden;

-- El rol administrador conserva el acceso total, incluida la capacidad nueva.
INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
  FROM rol r
 CROSS JOIN permiso p
 WHERE LOWER(r.nombre) = 'admin'
   AND p.clave = 'bitacora:consultar'
ON CONFLICT (id_rol, id_permiso) DO NOTHING;
