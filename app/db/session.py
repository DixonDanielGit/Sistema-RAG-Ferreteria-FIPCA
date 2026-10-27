"""Pool de conexiones a PostgreSQL (RNF-01, RNF-03).

La aplicacion usa dos bases independientes, cada una con su propio pool:

* ``ferreteria_rag``      -> catalogo de productos.
* ``ferreteria_usuarios`` -> usuarios, roles y bitacora.

Los pools se crean de forma diferida (en el primer uso) para que importar la
aplicacion no dependa de que la base este levantada.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from app.config import get_settings


class BaseDeDatosNoDisponible(RuntimeError):
    """No fue posible obtener una conexion a PostgreSQL."""


class _PoolDiferido:
    """Envuelve un ThreadedConnectionPool creado bajo demanda."""

    def __init__(self, nombre: str, obtener_dsn) -> None:
        self._nombre = nombre
        self._obtener_dsn = obtener_dsn
        self._pool: pg_pool.ThreadedConnectionPool | None = None
        self._candado = threading.Lock()

    def _crear(self) -> pg_pool.ThreadedConnectionPool:
        config = get_settings()
        dsn = self._obtener_dsn(config)

        if not dsn or not dsn.strip():
            raise BaseDeDatosNoDisponible(
                f"No hay cadena de conexion configurada para {self._nombre}"
            )

        try:
            return pg_pool.ThreadedConnectionPool(
                config.db_pool_minimo,
                config.db_pool_maximo,
                dsn=dsn,
                connect_timeout=5,
                application_name=f"ferreteria-api-{self._nombre}",
            )
        except psycopg2.Error as exc:
            raise BaseDeDatosNoDisponible(
                f"No se pudo conectar a {self._nombre}: {exc}"
            ) from exc

    def obtener(self):
        if self._pool is None:
            with self._candado:
                if self._pool is None:
                    self._pool = self._crear()
        return self._pool

    @contextmanager
    def cursor(self, *, commit: bool = True) -> Iterator[RealDictCursor]:
        """Entrega un cursor y gestiona la transaccion.

        Si el bloque termina sin error se confirma; si hay excepcion se
        revierte. La conexion siempre vuelve al pool.
        """
        pool = self.obtener()
        conexion = None
        try:
            conexion = pool.getconn()
        except pg_pool.PoolError as exc:
            raise BaseDeDatosNoDisponible(
                f"Sin conexiones disponibles para {self._nombre}"
            ) from exc

        try:
            with conexion:
                with conexion.cursor(cursor_factory=RealDictCursor) as cur:
                    yield cur
                if not commit:
                    conexion.rollback()
        finally:
            pool.putconn(conexion)

    def cerrar(self) -> None:
        with self._candado:
            if self._pool is not None:
                self._pool.closeall()
                self._pool = None


_pool_rag = _PoolDiferido("ferreteria_rag", lambda c: c.database_url_rag)
_pool_usuarios = _PoolDiferido("ferreteria_usuarios", lambda c: c.database_url_usuarios)


def cursor_rag(*, commit: bool = True):
    """Cursor sobre la base del catalogo."""
    return _pool_rag.cursor(commit=commit)


def cursor_usuarios(*, commit: bool = True):
    """Cursor sobre la base de usuarios y auditoria."""
    return _pool_usuarios.cursor(commit=commit)


def consultar_uno(sql: str, parametros: Iterable[Any] | None = None, *, rag: bool = False):
    """Ejecuta un SELECT y devuelve la primera fila como diccionario."""
    fabrica = cursor_rag if rag else cursor_usuarios
    with fabrica(commit=False) as cur:
        cur.execute(sql, tuple(parametros or ()))
        return cur.fetchone()


def consultar_todos(sql: str, parametros: Iterable[Any] | None = None, *, rag: bool = False):
    """Ejecuta un SELECT y devuelve todas las filas."""
    fabrica = cursor_rag if rag else cursor_usuarios
    with fabrica(commit=False) as cur:
        cur.execute(sql, tuple(parametros or ()))
        return cur.fetchall()


def ejecutar(sql: str, parametros: Iterable[Any] | None = None, *, rag: bool = False):
    """Ejecuta un INSERT/UPDATE/DELETE y devuelve la primera fila si la hay."""
    fabrica = cursor_rag if rag else cursor_usuarios
    with fabrica(commit=True) as cur:
        cur.execute(sql, tuple(parametros or ()))
        if cur.description is None:
            return None
        return cur.fetchone()


def cerrar_pools() -> None:
    """Cierra todos los pools (apagado ordenado de la aplicacion)."""
    _pool_rag.cerrar()
    _pool_usuarios.cerrar()
