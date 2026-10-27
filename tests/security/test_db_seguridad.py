"""Pruebas de seguridad de la base de datos (Semana 1).

Comprueban que PostgreSQL no acepte conexiones TCP sin contrasena, que no
haya privilegios heredados por PUBLIC y que la extension vectorial solo
exista en la base que la necesita.

Requieren el contenedor levantado; si no esta, se omiten.
"""

import os

import pytest

psycopg2 = pytest.importorskip("psycopg2")

RAG_DB = "ferreteria_rag"
USERS_DB = "ferreteria_usuarios"
MAINTENANCE_DB = os.getenv("TEST_DB_MAINTENANCE", "ferreteria")

CONNECTION = {
    "host": os.getenv("TEST_DB_HOST", "localhost"),
    "port": os.getenv("TEST_DB_PORT", "5432"),
    "user": os.getenv("TEST_DB_USER", "admin_ferreteria"),
    "password": os.getenv("TEST_DB_PASSWORD", "admin_ferreteria2026**"),
    "connect_timeout": 3,
}


def _connect(dbname, **overrides):
    parametros = {**CONNECTION, **overrides}
    try:
        return psycopg2.connect(dbname=dbname, **parametros)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")


@pytest.fixture
def rag():
    conn = _connect(RAG_DB)
    yield conn
    conn.close()


@pytest.fixture
def usuarios():
    conn = _connect(USERS_DB)
    yield conn
    conn.close()


@pytest.fixture
def mantenimiento():
    conn = _connect(MAINTENANCE_DB)
    yield conn
    conn.close()


def test_existe_un_unico_superusuario(mantenimiento):
    with mantenimiento.cursor() as cur:
        cur.execute("SELECT rolname FROM pg_roles WHERE rolsuper ORDER BY 1")
        superusuarios = [fila[0] for fila in cur.fetchall()]

    assert superusuarios == ["admin_ferreteria"], (
        f"Superusuarios inesperados: {superusuarios}"
    )


def test_pg_hba_no_confia_en_conexiones_tcp(mantenimiento):
    with mantenimiento.cursor() as cur:
        cur.execute(
            """
            SELECT type, database, user_name, address, auth_method
            FROM pg_hba_file_rules
            WHERE type = 'host'
            """
        )
        reglas = cur.fetchall()

    assert reglas, "No se pudieron leer las reglas de pg_hba"
    # Los trusts de 127.0.0.1/::1 solo son accesibles desde dentro del
    # contenedor; las conexiones externas deben exigir contrasena.
    inseguras = [
        r for r in reglas if r[4] == "trust" and r[3] not in ("127.0.0.1", "::1")
    ]
    assert not inseguras, f"Conexiones TCP sin contrasena: {inseguras}"


def test_conexion_sin_contrasena_es_rechazada():
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(dbname=MAINTENANCE_DB, **{**CONNECTION, "password": ""})


def test_contrasena_incorrecta_es_rechazada():
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(
            dbname=MAINTENANCE_DB, **{**CONNECTION, "password": "clave_incorrecta"}
        )


def test_public_no_puede_crear_objetos_en_el_esquema(mantenimiento):
    with mantenimiento.cursor() as cur:
        cur.execute(
            "SELECT nspacl FROM pg_namespace WHERE nspname = 'public'"
        )
        acl = cur.fetchone()[0] or []

    # En PG15+ el propietario es pg_database_owner; PUBLIC solo debe tener U.
    for privilegio in acl:
        if privilegio.startswith("="):
            permisos = privilegio.split("/")[0].lstrip("=")
            assert "C" not in permisos, "PUBLIC conserva CREATE sobre el esquema public"


def test_sin_permisos_otorgados_a_public(usuarios):
    with usuarios.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'PUBLIC'
              AND table_schema = 'public'
            """
        )
        concesiones = cur.fetchall()

    assert not concesiones, f"Tablas accesibles por PUBLIC: {concesiones}"


def test_vector_solo_esta_en_la_base_rag(rag, usuarios):
    with rag.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone() is not None

    with usuarios.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone() is None, "vector no debe instalarse en la base de usuarios"


def test_bitacora_sin_permisos_de_modificacion_para_otros_roles(usuarios):
    """Ningun rol puede modificar ni borrar la bitacora.

    El rol de la aplicacion solo recibe INSERT y SELECT; UPDATE, DELETE y
    TRUNCATE quedan reservados al propietario (y el trigger los bloquea
    incluso para el).
    """
    with usuarios.cursor() as cur:
        cur.execute(
            """
            SELECT grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_name = 'bitacora'
              AND grantee <> 'admin_ferreteria'
            """
        )
        concesiones = cur.fetchall()

    peligrosos = {
        (rol, privilegio)
        for rol, privilegio in concesiones
        if privilegio.upper() in {"UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"}
    }
    assert not peligrosos, f"Roles con permiso de modificacion sobre bitacora: {peligrosos}"


def test_la_aplicacion_solo_puede_insertar_y_consultar_la_bitacora(usuarios):
    with usuarios.cursor() as cur:
        cur.execute(
            """
            SELECT privilege_type
            FROM information_schema.role_table_grants
            WHERE table_name = 'bitacora' AND grantee = 'app_ferreteria'
            """
        )
        permisos = {fila[0].upper() for fila in cur.fetchall()}

    assert permisos == {"INSERT", "SELECT"}, f"Permisos inesperados: {permisos}"
