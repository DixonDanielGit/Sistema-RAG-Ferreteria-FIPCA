"""Aplica las migraciones incrementales sin borrar datos.

``init.sql`` solo corre al crear el volumen. Este comando actualiza una base
existente sin borrar sus datos y puede repetirse de forma segura.

Uso:
    ./venv/Scripts/python.exe scripts/aplicar_migracion.py 2_5
    ./venv/Scripts/python.exe scripts/aplicar_migracion.py 3_0
    ./venv/Scripts/python.exe scripts/aplicar_migracion.py 5_0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.config import get_settings  # noqa: E402  (tras ajustar sys.path)

MIGRACIONES = {
    "2_5": ("database_url_usuarios", "ferreteria_usuarios"),
    "3_0": ("database_url_rag", "ferreteria_rag"),
    "4_0": ("database_url_rag", "ferreteria_rag"),
    "5_0": ("database_url_usuarios", "ferreteria_usuarios"),
    "6_0": ("database_url_usuarios", "ferreteria_usuarios"),
}


def con_base_admin(dsn_admin: str, dsn_objetivo: str) -> str:
    """Cadena de administracion apuntando a la base de ``dsn_objetivo``.

    ``ADMIN_DATABASE_URL`` apunta a la base de mantenimiento (ferreteria); las
    tablas de usuarios viven en ferreteria_usuarios.
    """
    base = urlsplit(dsn_objetivo).path.lstrip("/")
    partes = urlsplit(dsn_admin)
    return urlunsplit((partes.scheme, partes.netloc, f"/{base}", partes.query, partes.fragment))


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument(
        "version",
        nargs="?",
        choices=tuple(MIGRACIONES),
        default="2_5",
        help="version de migracion (por defecto: 2_5)",
    )
    opciones = argumentos.parse_args()
    load_dotenv(RAIZ / ".env")
    config = get_settings()

    if not config.admin_database_url.strip():
        print("Falta ADMIN_DATABASE_URL en .env", file=sys.stderr)
        return 1

    atributo_dsn, nombre_base = MIGRACIONES[opciones.version]
    dsn_objetivo = getattr(config, atributo_dsn)
    if not dsn_objetivo.strip():
        print(f"Falta la URL de conexion para {nombre_base}", file=sys.stderr)
        return 1

    sql = RAIZ / "scripts" / f"migracion_{opciones.version}.sql"
    if not sql.is_file():
        print(f"No existe {sql}", file=sys.stderr)
        return 1

    dsn = con_base_admin(config.admin_database_url, dsn_objetivo)
    sentencias = sql.read_text(encoding="utf-8")

    try:
        with psycopg2.connect(dsn, connect_timeout=5) as conexion:
            conexion.autocommit = True
            with conexion.cursor() as cursor:
                cursor.execute(sentencias)
    except psycopg2.Error as exc:
        print(f"Error aplicando la migracion: {exc}", file=sys.stderr)
        return 1

    base = urlsplit(dsn).path.lstrip("/")
    print(f"Migracion {opciones.version} aplicada sobre {base} (idempotente).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
