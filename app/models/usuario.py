"""Acceso a datos de usuarios y roles (base ferreteria_usuarios).

Todas las consultas usan parametros ligados (``%s``); ninguna concatena texto
del usuario en el SQL. Esto, sumado a los permisos del rol de aplicacion, es la
defensa principal contra inyeccion SQL (RNF-02.2).
"""

from __future__ import annotations

from typing import Any

from app.db.session import consultar_todos, consultar_uno, ejecutar

COLUMNAS_USUARIO = """
    u.id,
    u.id_rol,
    u.cedula,
    u.nombre,
    u.apellido,
    u.usuario,
    u.correo,
    u.activo,
    r.nombre AS rol
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


def conflictos(usuario: str, correo: str, cedula: str) -> list[str]:
    """Devuelve los campos que ya estan registrados en otra cuenta."""
    fila = consultar_uno(
        """
        SELECT
            EXISTS (SELECT 1 FROM usuarios WHERE LOWER(usuario) = LOWER(%s)) AS usuario,
            EXISTS (SELECT 1 FROM usuarios WHERE LOWER(correo) = LOWER(%s))  AS correo,
            EXISTS (SELECT 1 FROM usuarios WHERE LOWER(cedula) = LOWER(%s))  AS cedula
        """,
        (usuario, correo, cedula),
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


def listar_roles() -> list[dict[str, Any]]:
    return consultar_todos("SELECT id_rol, nombre, descripcion FROM rol ORDER BY id_rol")


def id_de_rol(nombre: str) -> int | None:
    fila = consultar_uno("SELECT id_rol FROM rol WHERE LOWER(nombre) = LOWER(%s)", (nombre,))
    return int(fila["id_rol"]) if fila else None
