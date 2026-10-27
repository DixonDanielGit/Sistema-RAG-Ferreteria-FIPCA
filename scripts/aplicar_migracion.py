"""Aplica scripts/migracion_2_5.sql sobre la base de usuarios.

Se usa cuando el volumen de PostgreSQL ya existe (init.sql solo corre al crear
el volumen por primera vez). Es idempotente.

Uso:
    ./venv/Scripts/python.exe scripts/aplicar_migracion.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.config import get_settings  # noqa: E402  (tras ajustar sys.path)

SQL = RAIZ / "scripts" / "migracion_2_5.sql"


def con_base_admin(dsn_admin: str, dsn_objetivo: str) -> str:
    """Cadena de administracion apuntando a la base de ``dsn_objetivo``.

    ``ADMIN_DATABASE_URL`` apunta a la base de mantenimiento (ferreteria); las
    tablas de usuarios viven en ferreteria_usuarios.
    """
    base = urlsplit(dsn_objetivo).path.lstrip("/")
    partes = urlsplit(dsn_admin)
    return urlunsplit((partes.scheme, partes.netloc, f"/{base}", partes.query, partes.fragment))


def main() -> int:
    load_dotenv(RAIZ / ".env")
    config = get_settings()

    if not config.admin_database_url.strip():
        print("Falta ADMIN_DATABASE_URL en .env", file=sys.stderr)
        return 1

    if not SQL.is_file():
        print(f"No existe {SQL}", file=sys.stderr)
        return 1

    dsn = con_base_admin(config.admin_database_url, config.database_url_usuarios)
    sentencias = SQL.read_text(encoding="utf-8")

    try:
        with psycopg2.connect(dsn, connect_timeout=5) as conexion:
            conexion.autocommit = True
            with conexion.cursor() as cursor:
                cursor.execute(sentencias)
    except psycopg2.Error as exc:
        print(f"Error aplicando la migracion: {exc}", file=sys.stderr)
        return 1

    base = urlsplit(dsn).path.lstrip("/")
    print(f"Migracion 2.5 aplicada sobre {base} (idempotente).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
