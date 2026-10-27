"""Configuracion comun de la suite de pruebas.

Las pruebas de integracion no tocan las bases reales: al inicio de la sesion
se clonan ``ferreteria_rag`` y ``ferreteria_usuarios`` como
``ferreteria_rag_test`` y ``ferreteria_usuarios_test``, y se eliminan al
terminar. Asi los datos de prueba no se mezclan con el entorno de desarrollo.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

RAG_PLANTILLA = "ferreteria_rag"
USUARIOS_PLANTILLA = "ferreteria_usuarios"
RAG_PRUEBA = "ferreteria_rag_test"
USUARIOS_PRUEBA = "ferreteria_usuarios_test"


def con_base(dsn: str, base: str) -> str:
    """Reemplaza el nombre de la base en una cadena de conexion."""
    partes = urlsplit(dsn)
    return urlunsplit((partes.scheme, partes.netloc, f"/{base}", partes.query, partes.fragment))


def _dsn_admin() -> str:
    return os.getenv("ADMIN_DATABASE_URL", "").strip()


def conexion_admin(base: str = USUARIOS_PRUEBA):
    """Conexion con la cuenta de administracion a una base concreta."""
    psycopg2 = pytest.importorskip("psycopg2")
    dsn = con_base(_dsn_admin(), base)
    conexion = psycopg2.connect(dsn, connect_timeout=3)
    conexion.autocommit = True
    return conexion


@pytest.fixture(scope="session")
def bases_de_prueba():
    """Clona las bases reales y apunta la aplicacion a las copias."""
    psycopg2 = pytest.importorskip("psycopg2")

    if not _dsn_admin():
        pytest.skip("Falta ADMIN_DATABASE_URL en .env")

    for variable in ("DATABASE_URL_RAG", "DATABASE_URL_USUARIOS"):
        if not os.getenv(variable):
            pytest.skip(f"Falta {variable} en .env")

    try:
        conexion = conexion_admin("postgres")
    except psycopg2.Error as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")

    try:
        with conexion.cursor() as cur:
            for plantilla, prueba in (
                (RAG_PLANTILLA, RAG_PRUEBA),
                (USUARIOS_PLANTILLA, USUARIOS_PRUEBA),
            ):
                cur.execute(f'DROP DATABASE IF EXISTS "{prueba}" WITH (FORCE)')
                cur.execute(f'CREATE DATABASE "{prueba}" TEMPLATE "{plantilla}"')
    except psycopg2.Error as exc:
        pytest.skip(
            "No se pudieron clonar las bases de prueba "
            f"(cierre pgAdmin si tiene sesiones abiertas): {exc}"
        )
    finally:
        conexion.close()

    os.environ["DATABASE_URL_RAG"] = con_base(
        os.environ["DATABASE_URL_RAG"], RAG_PRUEBA
    )
    os.environ["DATABASE_URL_USUARIOS"] = con_base(
        os.environ["DATABASE_URL_USUARIOS"], USUARIOS_PRUEBA
    )

    yield

    try:
        from app.db.session import cerrar_pools

        cerrar_pools()
    except Exception:  # noqa: BLE001 - la limpieza no debe fallar la sesion
        pass

    try:
        conexion = conexion_admin("postgres")
        with conexion.cursor() as cur:
            for prueba in (RAG_PRUEBA, USUARIOS_PRUEBA):
                cur.execute(f'DROP DATABASE IF EXISTS "{prueba}" WITH (FORCE)')
        conexion.close()
    except psycopg2.Error:
        pass


@pytest.fixture(scope="session")
def cliente(bases_de_prueba):
    """Cliente HTTP de pruebas sobre la aplicacion FastAPI."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as cliente_http:
        yield cliente_http


@pytest.fixture(scope="session")
def conexion_limpieza(bases_de_prueba):
    """Conexion de administracion reutilizada en toda la sesion."""
    conexion = conexion_admin()
    yield conexion
    conexion.close()


@pytest.fixture
def usuarios_limpios(conexion_limpieza):
    """Vacia usuarios y bitacora antes de cada prueba.

    Se desactivan temporalmente los triggers de inmutabilidad porque son
    pruebas: en produccion la bitacora jamas se borra.
    """
    with conexion_limpieza.cursor() as cur:
        cur.execute("ALTER TABLE bitacora DISABLE TRIGGER USER")
        cur.execute("TRUNCATE bitacora, usuarios RESTART IDENTITY CASCADE")
        cur.execute("ALTER TABLE bitacora ENABLE TRIGGER USER")

    yield


@pytest.fixture
def crear_cuenta(usuarios_limpios):
    """Fabrica cuentas de prueba directamente en la base."""
    from app.core.security import hash_password
    from app.models import usuario as modelo

    contador = {"n": 0}

    def _crear(
        usuario: str = "supervisor",
        password: str = "ClaveSegura123",
        rol: str = "admin",
        activo: bool = True,
        nombre: str = "Ana",
        apellido: str = "Perez",
    ) -> dict:
        contador["n"] += 1
        sufijo = contador["n"]
        id_rol = modelo.id_de_rol(rol)
        assert id_rol is not None, f"El rol {rol} no existe en la base"

        creado = modelo.crear(
            id_rol=id_rol,
            cedula=f"V-{10000000 + sufijo}",
            nombre=nombre,
            apellido=apellido,
            usuario=usuario,
            password_hash=hash_password(password),
            correo=f"{usuario}@ferreteria.test",
        )

        if not activo:
            modelo.cambiar_estado(creado["id"], False)
            creado["activo"] = False

        return {
            "id": creado["id"],
            "usuario": usuario,
            "correo": f"{usuario}@ferreteria.test",
            "password": password,
            "rol": rol,
            "activo": activo,
        }

    return _crear


@pytest.fixture
def token_de(cliente):
    """Autentica una cuenta y devuelve su token."""

    def _token(cuenta: dict) -> str:
        respuesta = cliente.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["access_token"]

    return _token
