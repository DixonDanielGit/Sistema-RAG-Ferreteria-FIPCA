"""Acceso a datos de la bitacora de auditoria (RF-05).

La tabla es inmutable por diseno: este modulo solo inserta y consulta.
Cualquier intento de modificar o borrar un registro falla en la base.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db.session import consultar_todos, ejecutar


def registrar(
    *,
    id_usuario: int | None,
    accion: str,
    ip: str | None = None,
    modulo: str | None = None,
) -> None:
    """Anade un evento a la bitacora.

    ``id_usuario`` admite None para auditar intentos de login fallidos con
    usuarios inexistentes (ver init.sql).
    """
    accion_limpia = (accion or "").strip()
    if not accion_limpia:
        raise ValueError("La accion auditada no puede estar vacia")

    ejecutar(
        """
        INSERT INTO bitacora (id_usuario, accion, ip, modulo)
        VALUES (%s, %s, %s, %s)
        """,
        (
            id_usuario,
            accion_limpia[:1000],
            ip[:45] if ip else None,
            modulo[:50] if modulo else None,
        ),
    )


def listar(
    *,
    desde: date | None = None,
    hasta: date | None = None,
    id_usuario: int | None = None,
    modulo: str | None = None,
    ip: str | None = None,
    limite: int = 100,
) -> list[dict[str, Any]]:
    """Consulta la bitacora con los filtros del visor de auditoria (RF-05.2)."""
    condiciones: list[str] = []
    parametros: list[Any] = []

    if desde:
        condiciones.append("b.fecha >= %s")
        parametros.append(desde)
    if hasta:
        condiciones.append("b.fecha <= %s")
        parametros.append(hasta)
    if id_usuario:
        condiciones.append("b.id_usuario = %s")
        parametros.append(id_usuario)
    if modulo:
        condiciones.append("b.modulo = %s")
        parametros.append(modulo)
    if ip:
        condiciones.append("b.ip = %s")
        parametros.append(ip)

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    limite = max(1, min(int(limite), 500))
    parametros.append(limite)

    return consultar_todos(
        f"""
        SELECT b.id_bitacora, b.id_usuario, b.fecha, b.hora,
               b.accion, b.ip, b.modulo,
               u.usuario AS nombre_usuario
        FROM bitacora b
        LEFT JOIN usuarios u ON u.id = b.id_usuario
        {where}
        ORDER BY b.id_bitacora DESC
        LIMIT %s
        """,
        parametros,
    )


def ultimos(limite: int = 20) -> list[dict[str, Any]]:
    return listar(limite=limite)
