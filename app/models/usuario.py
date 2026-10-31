"""Acceso a datos de usuarios y roles (base ferreteria_usuarios).

Todas las consultas usan parametros ligados (``%s``); ninguna concatena texto
del usuario en el SQL. Esto, sumado a los permisos del rol de aplicacion, es la
defensa principal contra inyeccion SQL (RNF-02.2).
"""

from __future__ import annotations

from typing import Any

import psycopg2

from app.db.session import consultar_todos, consultar_uno, cursor_usuarios, ejecutar

COLUMNAS_USUARIO = """
    u.id,
    u.id_rol,
    u.cedula,
    u.nombre,
    u.apellido,
    u.usuario,
    u.correo,
    u.activo,
    (u.imagen_perfil IS NOT NULL) AS tiene_imagen,
    r.nombre AS rol,
    r.descripcion AS rol_descripcion,
    ARRAY(
        SELECT p.clave
          FROM rol_permiso rp
          JOIN permiso p ON p.id_permiso = rp.id_permiso
         WHERE rp.id_rol = r.id_rol
         ORDER BY p.orden, p.clave
    ) AS permisos
"""


def buscar_por_identificador(identificador: str) -> dict[str, Any] | None:
    """Busca una cuenta por nombre de usuario o correo (sin distinguir mayusculas)."""
    return consultar_uno(
        f"""
        SELECT {COLUMNAS_USUARIO}, u.password
        FROM usuarios u
        JOIN rol r ON r.id_rol = u.id_rol
        WHERE LOWER(u.usuario) = LOWER(%s)
           OR LOWER(u.correo) = LOWER(%s)
        LIMIT 1
        """,
        (identificador, identificador),
    )


def buscar_por_id(id_usuario: int) -> dict[str, Any] | None:
    """Datos publicos de una cuenta (sin el hash de la contrasena)."""
    return consultar_uno(
        f"""
        SELECT {COLUMNAS_USUARIO}
        FROM usuarios u
        JOIN rol r ON r.id_rol = u.id_rol
        WHERE u.id = %s
        """,
        (id_usuario,),
    )


def contar() -> int:
    fila = consultar_uno("SELECT COUNT(*) AS total FROM usuarios")
    return int(fila["total"]) if fila else 0


def buscar_por_correo(correo: str) -> dict[str, Any] | None:
    """Busca una cuenta por correo exacto (sin distinguir mayusculas)."""
    return consultar_uno(
        f"""
        SELECT {COLUMNAS_USUARIO}
        FROM usuarios u
        JOIN rol r ON r.id_rol = u.id_rol
        WHERE LOWER(u.correo) = LOWER(%s)
        LIMIT 1
        """,
        (correo,),
    )


def conflictos(
    usuario: str, correo: str, cedula: str, *, id_excluir: int | None = None
) -> list[str]:
    """Devuelve los campos que ya estan registrados en otra cuenta."""
    fila = consultar_uno(
        """
        SELECT
            EXISTS (
                SELECT 1 FROM usuarios
                 WHERE LOWER(usuario) = LOWER(%s)
                   AND (%s::integer IS NULL OR id <> %s)
            ) AS usuario,
            EXISTS (
                SELECT 1 FROM usuarios
                 WHERE LOWER(correo) = LOWER(%s)
                   AND (%s::integer IS NULL OR id <> %s)
            ) AS correo,
            EXISTS (
                SELECT 1 FROM usuarios
                 WHERE LOWER(cedula) = LOWER(%s)
                   AND (%s::integer IS NULL OR id <> %s)
            ) AS cedula
        """,
        (
            usuario, id_excluir, id_excluir,
            correo, id_excluir, id_excluir,
            cedula, id_excluir, id_excluir,
        ),
    )
    if not fila:
        return []
    return [campo for campo in ("usuario", "correo", "cedula") if fila[campo]]


def crear(
    *,
    id_rol: int,
    cedula: str,
    nombre: str,
    apellido: str,
    usuario: str,
    password_hash: str,
    correo: str,
) -> dict[str, Any]:
    """Inserta una cuenta y devuelve sus datos publicos."""
    fila = ejecutar(
        """
        INSERT INTO usuarios
            (id_rol, cedula, nombre, apellido, usuario, password, correo)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (id_rol, cedula, nombre, apellido, usuario, password_hash, correo),
    )
    return buscar_por_id(int(fila["id"]))  # type: ignore[index]


def actualizar_password(id_usuario: int, password_hash: str) -> bool:
    fila = ejecutar(
        """
        UPDATE usuarios SET password = %s WHERE id = %s RETURNING id
        """,
        (password_hash, id_usuario),
    )
    return fila is not None


def cambiar_estado(id_usuario: int, activo: bool) -> bool:
    """Activa o desactiva una cuenta (no se elimina: conserva la auditoria)."""
    fila = ejecutar(
        "UPDATE usuarios SET activo = %s WHERE id = %s RETURNING id",
        (activo, id_usuario),
    )
    return fila is not None


def listar_usuarios() -> list[dict[str, Any]]:
    """Lista cuentas sin incluir hashes ni contenido de imagen."""
    return consultar_todos(
        f"""
        SELECT {COLUMNAS_USUARIO}
          FROM usuarios u
          JOIN rol r ON r.id_rol = u.id_rol
         ORDER BY LOWER(u.apellido), LOWER(u.nombre), u.id
        """
    )


def actualizar_perfil(
    id_usuario: int,
    *,
    cedula: str,
    nombre: str,
    apellido: str,
    usuario: str,
    correo: str,
) -> dict[str, Any] | None:
    fila = ejecutar(
        """
        UPDATE usuarios
           SET cedula = %s, nombre = %s, apellido = %s, usuario = %s, correo = %s
         WHERE id = %s
        RETURNING id
        """,
        (cedula, nombre, apellido, usuario, correo, id_usuario),
    )
    return buscar_por_id(int(fila["id"])) if fila else None


def actualizar_usuario_admin(
    id_usuario: int,
    *,
    cedula: str,
    nombre: str,
    apellido: str,
    usuario: str,
    correo: str,
    rol: str,
) -> str:
    """Actualiza datos de cuenta y rol de forma atomica, protegiendo al ultimo admin."""
    with cursor_usuarios() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(917, 5)")
        cur.execute(
            """
            SELECT u.activo, LOWER(r.nombre) AS rol
              FROM usuarios u
              JOIN rol r ON r.id_rol = u.id_rol
             WHERE u.id = %s
             FOR UPDATE OF u
            """,
            (id_usuario,),
        )
        actual = cur.fetchone()
        if actual is None:
            return "no_encontrado"

        cur.execute("SELECT id_rol FROM rol WHERE LOWER(nombre) = LOWER(%s)", (rol,))
        destino = cur.fetchone()
        if destino is None:
            return "rol_invalido"

        if actual["rol"] == "admin" and actual["activo"] and rol != "admin":
            cur.execute(
                """
                SELECT COUNT(*) AS total
                  FROM usuarios u
                  JOIN rol r ON r.id_rol = u.id_rol
                 WHERE u.activo AND LOWER(r.nombre) = 'admin'
                """
            )
            if cur.fetchone()["total"] <= 1:
                return "ultimo_admin"

        cur.execute(
            """
            UPDATE usuarios
               SET id_rol = %s, cedula = %s, nombre = %s, apellido = %s,
                   usuario = %s, correo = %s
             WHERE id = %s
            """,
            (destino["id_rol"], cedula, nombre, apellido, usuario, correo, id_usuario),
        )
    return "actualizado"


def guardar_imagen(id_usuario: int, imagen: bytes) -> bool:
    fila = ejecutar(
        "UPDATE usuarios SET imagen_perfil = %s WHERE id = %s RETURNING id",
        (psycopg2.Binary(imagen), id_usuario),
    )
    return fila is not None


def obtener_imagen(id_usuario: int) -> bytes | None:
    fila = consultar_uno(
        "SELECT imagen_perfil FROM usuarios WHERE id = %s",
        (id_usuario,),
    )
    return bytes(fila["imagen_perfil"]) if fila and fila["imagen_perfil"] else None


def eliminar_imagen(id_usuario: int) -> bool:
    fila = ejecutar(
        "UPDATE usuarios SET imagen_perfil = NULL WHERE id = %s RETURNING id",
        (id_usuario,),
    )
    return fila is not None


def actualizar_rol_admin(id_usuario: int, rol: str) -> str:
    """Cambia el rol sin permitir retirar el ultimo administrador activo."""
    with cursor_usuarios() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(917, 5)")
        cur.execute(
            """
            SELECT u.id_rol, u.activo, LOWER(r.nombre) AS rol
              FROM usuarios u
              JOIN rol r ON r.id_rol = u.id_rol
             WHERE u.id = %s
             FOR UPDATE OF u
            """,
            (id_usuario,),
        )
        actual = cur.fetchone()
        if actual is None:
            return "no_encontrado"

        cur.execute("SELECT id_rol FROM rol WHERE LOWER(nombre) = LOWER(%s)", (rol,))
        destino = cur.fetchone()
        if destino is None:
            return "rol_invalido"

        if actual["rol"] == "admin" and actual["activo"] and rol != "admin":
            cur.execute(
                """
                SELECT COUNT(*) AS total
                  FROM usuarios u
                  JOIN rol r ON r.id_rol = u.id_rol
                 WHERE u.activo AND LOWER(r.nombre) = 'admin'
                """
            )
            if cur.fetchone()["total"] <= 1:
                return "ultimo_admin"

        cur.execute(
            "UPDATE usuarios SET id_rol = %s WHERE id = %s",
            (destino["id_rol"], id_usuario),
        )
    return "actualizado"


def actualizar_estado_admin(id_usuario: int, activo: bool) -> str:
    """Activa/desactiva una cuenta y protege al ultimo administrador activo."""
    with cursor_usuarios() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(917, 5)")
        cur.execute(
            """
            SELECT u.activo, LOWER(r.nombre) AS rol
              FROM usuarios u
              JOIN rol r ON r.id_rol = u.id_rol
             WHERE u.id = %s
             FOR UPDATE OF u
            """,
            (id_usuario,),
        )
        actual = cur.fetchone()
        if actual is None:
            return "no_encontrado"

        if not activo and actual["activo"] and actual["rol"] == "admin":
            cur.execute(
                """
                SELECT COUNT(*) AS total
                  FROM usuarios u
                  JOIN rol r ON r.id_rol = u.id_rol
                 WHERE u.activo AND LOWER(r.nombre) = 'admin'
                """
            )
            if cur.fetchone()["total"] <= 1:
                return "ultimo_admin"

        cur.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, id_usuario))
    return "actualizado"


def listar_roles() -> list[dict[str, Any]]:
    return consultar_todos(
        """
        SELECT r.id_rol, r.nombre, r.descripcion, r.protegido,
               COUNT(u.id)::integer AS usuarios_asignados,
               ARRAY(
                   SELECT p.clave
                     FROM rol_permiso rp
                     JOIN permiso p ON p.id_permiso = rp.id_permiso
                    WHERE rp.id_rol = r.id_rol
                    ORDER BY p.orden, p.clave
               ) AS permisos
          FROM rol r
          LEFT JOIN usuarios u ON u.id_rol = r.id_rol
         GROUP BY r.id_rol
         ORDER BY LOWER(r.nombre), r.id_rol
        """
    )


def listar_permisos() -> list[dict[str, Any]]:
    return consultar_todos(
        "SELECT clave, nombre, descripcion, orden FROM permiso ORDER BY orden, clave"
    )


def crear_rol(nombre: str, descripcion: str, permisos: list[str]) -> int:
    """Crea un rol y sus capacidades de forma atomica."""
    with cursor_usuarios() as cur:
        cur.execute(
            """
            INSERT INTO rol (nombre, descripcion)
            VALUES (%s, %s)
            RETURNING id_rol
            """,
            (nombre, descripcion or None),
        )
        id_rol = int(cur.fetchone()["id_rol"])
        for clave in permisos:
            cur.execute(
                """
                INSERT INTO rol_permiso (id_rol, id_permiso)
                SELECT %s, id_permiso FROM permiso WHERE clave = %s
                """,
                (id_rol, clave),
            )
    return id_rol


def actualizar_rol(
    id_rol: int, nombre: str, descripcion: str, permisos: list[str]
) -> str:
    """Actualiza un rol editable y su conjunto de capacidades en una transaccion."""
    with cursor_usuarios() as cur:
        cur.execute("SELECT protegido FROM rol WHERE id_rol = %s FOR UPDATE", (id_rol,))
        actual = cur.fetchone()
        if actual is None:
            return "no_encontrado"
        if actual["protegido"]:
            return "protegido"

        cur.execute(
            "UPDATE rol SET nombre = %s, descripcion = %s WHERE id_rol = %s",
            (nombre, descripcion or None, id_rol),
        )
        cur.execute("DELETE FROM rol_permiso WHERE id_rol = %s", (id_rol,))
        for clave in permisos:
            cur.execute(
                """
                INSERT INTO rol_permiso (id_rol, id_permiso)
                SELECT %s, id_permiso FROM permiso WHERE clave = %s
                """,
                (id_rol, clave),
            )
    return "actualizado"


def eliminar_rol(id_rol: int) -> str:
    """Elimina un rol no protegido y sin cuentas asignadas."""
    with cursor_usuarios() as cur:
        cur.execute("SELECT protegido FROM rol WHERE id_rol = %s FOR UPDATE", (id_rol,))
        actual = cur.fetchone()
        if actual is None:
            return "no_encontrado"
        if actual["protegido"]:
            return "protegido"

        cur.execute("SELECT EXISTS (SELECT 1 FROM usuarios WHERE id_rol = %s)", (id_rol,))
        if cur.fetchone()["exists"]:
            return "asignado"

        cur.execute("DELETE FROM rol WHERE id_rol = %s", (id_rol,))
    return "eliminado"


def id_de_rol(nombre: str) -> int | None:
    fila = consultar_uno("SELECT id_rol FROM rol WHERE LOWER(nombre) = LOWER(%s)", (nombre,))
    return int(fila["id_rol"]) if fila else None
