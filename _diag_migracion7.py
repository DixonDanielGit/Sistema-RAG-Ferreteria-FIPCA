"""Prueba temporal: aplica migracion_7_0 sobre una base desechable."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from app.config import get_settings

config = get_settings()
base = urlsplit(config.database_url_rag).path.lstrip("/")
partes = urlsplit(config.admin_database_url)
nombre_prueba = "ferreteria_rag_mig7"

dsn_admin = urlunsplit((partes.scheme, partes.netloc, "/postgres", "", ""))
dsn_prueba = urlunsplit((partes.scheme, partes.netloc, f"/{nombre_prueba}", "", ""))
sql = (RAIZ / "scripts" / "migracion_7_0.sql").read_text(encoding="utf-8")


def administrar(*sentencias: str) -> None:
    conexion = psycopg2.connect(dsn_admin, connect_timeout=5)
    conexion.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    with conexion.cursor() as cursor:
        for sentencia in sentencias:
            cursor.execute(sentencia)
    conexion.close()


administrar(
    f'DROP DATABASE IF EXISTS {nombre_prueba} WITH (FORCE)',
    f'CREATE DATABASE {nombre_prueba} TEMPLATE "{base}"',
)
try:
    with psycopg2.connect(dsn_prueba, connect_timeout=5) as conexion:
        conexion.autocommit = True
        with conexion.cursor() as cur:
            cur.execute(sql)
            cur.execute(sql)  # idempotencia
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            print("tablas:", [f[0] for f in cur.fetchall()])
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'productos' ORDER BY ordinal_position"
            )
            print("columnas productos:", [f[0] for f in cur.fetchall()])
            cur.execute("SELECT * FROM configuracion_stock")
            print("configuracion_stock:", cur.fetchone())
finally:
    administrar(f'DROP DATABASE IF EXISTS {nombre_prueba} WITH (FORCE)')
    print("base de prueba eliminada")
