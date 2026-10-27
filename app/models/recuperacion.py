"""Acceso a datos de los tokens de recuperacion de contrasena (Adenda 1).

Igual que el resto de modelos, todas las consultas usan parametros ligados
(``%s``). El token que ve el usuario nunca se guarda: solo su SHA-256.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.db.session import consultar_uno, ejecutar

COLUMNAS = """
    t.id,
    t.id_usuario,
    t.token_hash,
    t.creado_en,
    t.expira_en,
    t.usado_en,
    u.usuario,
    u.correo
"""


def crear(id_usuario: int, token_hash: str, minutos: int) -> dict[str, Any]:
    """Registra un token nuevo e invalida los anteriores del mismo usuario.

    Ambas sentencias van en la misma transaccion: no puede quedar un token
    viejo vivo junto al nuevo.
    """
    from app.db.session import cursor_usuarios

    with cursor_usuarios() as cur:
        cur.execute(
            """
            UPDATE tokens_recuperacion
               SET usado_en = NOW()
             WHERE id_usuario = %s
               AND usado_en IS NULL
            """,
            (id_usuario,),
        )
        cur.execute(
            """
            INSERT INTO tokens_recuperacion (id_usuario, token_hash, expira_en)
            VALUES (%s, %s, NOW() + %s)
            RETURNING id, id_usuario, token_hash, creado_en, expira_en, usado_en
            """,
            (id_usuario, token_hash, timedelta(minutes=minutos)),
        )
        fila = cur.fetchone()

    if fila is None:  # pragma: no cover - RETURNING siempre devuelve la fila
        raise RuntimeError("No se pudo registrar el token de recuperacion")
    return dict(fila)


def buscar_vigente(token_hash: str) -> dict[str, Any] | None:
    """Devuelve el token si existe, no se uso y no ha caducado."""
    return consultar_uno(
        f"""
        SELECT {COLUMNAS}
        FROM tokens_recuperacion t
        JOIN usuarios u ON u.id = t.id_usuario
        WHERE t.token_hash = %s
          AND t.usado_en IS NULL
          AND t.expira_en > NOW()
        LIMIT 1
        """,
        (token_hash,),
    )


def consumir(token_hash: str) -> int | None:
    """Marca el token como usado y devuelve el ``id_usuario``.

    El ``UPDATE`` condicional es la garantia de un solo uso: si dos peticiones
    llegan a la vez, solo una encuentra ``usado_en IS NULL`` y obtiene fila.
    """
    fila = ejecutar(
        """
        UPDATE tokens_recuperacion
           SET usado_en = NOW()
         WHERE token_hash = %s
           AND usado_en IS NULL
           AND expira_en > NOW()
        RETURNING id_usuario
        """,
        (token_hash,),
    )
    return int(fila["id_usuario"]) if fila else None


def invalidar_de_usuario(id_usuario: int) -> int:
    """Invalida todos los tokens pendientes de una cuenta."""
    from app.db.session import cursor_usuarios

    with cursor_usuarios() as cur:
        cur.execute(
            """
            UPDATE tokens_recuperacion
               SET usado_en = NOW()
             WHERE id_usuario = %s
               AND usado_en IS NULL
            """,
            (id_usuario,),
        )
        return cur.rowcount
