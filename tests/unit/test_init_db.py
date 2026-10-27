"""Pruebas de caja blanca del esquema inicial definido en init.sql.

Verifican que las dos bases de datos del MER se creen correctamente, que
las tablas vivan en la base que les corresponde y que las reglas de
negocio (IVA fijo, valores no negativos, bitacora inmutable) se cumplan.

Requieren el contenedor de PostgreSQL levantado:

    docker compose up -d

Si la base no esta disponible, las pruebas se marcan como omitidas para
no romper la suite en equipos sin Docker.
"""

import os
import uuid

import pytest

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import errors  # noqa: E402  (depende del importorskip)

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

TABLAS_RAG = {"archivos_subidos", "proveedores", "categoria", "productos"}
TABLAS_USUARIOS = {"rol", "usuarios", "bitacora"}


def _connect(dbname):
    """Abre una conexion o marca la prueba como omitida si no hay servidor."""
    try:
        conn = psycopg2.connect(dbname=dbname, **CONNECTION)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    conn.autocommit = False
    return conn


@pytest.fixture
def rag():
    conn = _connect(RAG_DB)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def usuarios():
    conn = _connect(USERS_DB)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def mantenimiento():
    conn = _connect(MAINTENANCE_DB)
    yield conn
    conn.rollback()
    conn.close()


def _tablas(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        return {fila[0] for fila in cur.fetchall()}


def _columnas(conn, tabla):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (tabla,),
        )
        return {fila[0] for fila in cur.fetchall()}


def _crear_usuario(conn):
    """Inserta un usuario de prueba y devuelve su id."""
    sufijo = uuid.uuid4().hex[:12]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios
                (id_rol, cedula, nombre, apellido, usuario, password, correo)
            SELECT id_rol, %s, 'Ana', 'Perez', %s, 'hash_de_prueba', %s
            FROM rol WHERE nombre = 'admin'
            RETURNING id
            """,
            (f"V-{sufijo}", f"usuario_{sufijo}", f"{sufijo}@ferreteria.com"),
        )
        return cur.fetchone()[0]


# ---------------------------------------------------------------------
# Bases de datos
# ---------------------------------------------------------------------

def test_existen_las_dos_bases_de_datos(mantenimiento):
    with mantenimiento.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database")
        bases = {fila[0] for fila in cur.fetchall()}

    assert RAG_DB in bases, "Falta la base principal del sistema RAG"
    assert USERS_DB in bases, "Falta la base de usuarios"


def test_tablas_en_la_base_rag(rag):
    assert TABLAS_RAG.issubset(_tablas(rag))


def test_tablas_en_la_base_usuarios(usuarios):
    assert TABLAS_USUARIOS.issubset(_tablas(usuarios))


def test_las_tablas_no_se_cruzan_entre_bases(rag, usuarios):
    assert TABLAS_USUARIOS.isdisjoint(_tablas(rag))
    assert TABLAS_RAG.isdisjoint(_tablas(usuarios))


# ---------------------------------------------------------------------
# Extensiones e indices
# ---------------------------------------------------------------------

def test_extension_vector_instalada_en_rag(rag):
    with rag.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone() is not None


def test_indice_hnsw_sobre_descripcion_vectorial(rag):
    with rag.cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'productos'
              AND indexdef ILIKE '%hnsw%'
            """
        )
        assert cur.fetchone() is not None, "Falta el indice HNSW de pgvector"


# ---------------------------------------------------------------------
# Columnas exigidas por el SRS
# ---------------------------------------------------------------------

def test_productos_tiene_columnas_del_srs(rag):
    assert {"codigo", "iva", "descuentos"} <= _columnas(rag, "productos")


def test_usuarios_tiene_columna_activo(usuarios):
    assert "activo" in _columnas(usuarios, "usuarios")


def test_bitacora_permite_filtrar_por_ip_y_modulo(usuarios):
    assert {"ip", "modulo"} <= _columnas(usuarios, "bitacora")


def test_roles_admin_y_ventas_sembrados(usuarios):
    with usuarios.cursor() as cur:
        cur.execute("SELECT nombre FROM rol")
        roles = {fila[0] for fila in cur.fetchall()}

    assert {"admin", "ventas"} <= roles


# ---------------------------------------------------------------------
# Reglas de negocio de productos
# ---------------------------------------------------------------------

def test_valores_por_defecto_de_producto(rag):
    with rag.cursor() as cur:
        cur.execute(
            """
            INSERT INTO productos (nombre, precio)
            VALUES ('Martillo de prueba', 12.50)
            RETURNING "iva", descuentos, stock
            """
        )
        iva, descuentos, stock = cur.fetchone()

    assert str(iva) == "16.00"
    assert str(descuentos) == "0.00"
    assert stock == 0


def test_iva_distinto_de_16_es_rechazado(rag):
    with rag.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO productos (nombre, precio, "iva")
                VALUES ('Producto IVA invalido', 10.00, 21.00)
                """
            )


def test_precio_negativo_es_rechazado(rag):
    with rag.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO productos (nombre, precio)
                VALUES ('Producto con precio negativo', -1.00)
                """
            )


def test_stock_negativo_es_rechazado(rag):
    with rag.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO productos (nombre, precio, stock)
                VALUES ('Producto con stock negativo', 5.00, -1)
                """
            )


def test_codigo_de_producto_es_unico(rag):
    with rag.cursor() as cur:
        cur.execute(
            "INSERT INTO productos (codigo, nombre, precio) VALUES ('SKU-1', 'A', 1.00)"
        )
        with pytest.raises(errors.UniqueViolation):
            cur.execute(
                "INSERT INTO productos (codigo, nombre, precio) VALUES ('SKU-1', 'B', 2.00)"
            )


# ---------------------------------------------------------------------
# Bitacora: inmutabilidad y auditoria
# ---------------------------------------------------------------------

def test_bitacora_admite_usuario_nulo_para_login_fallido(usuarios):
    with usuarios.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bitacora (accion, ip, modulo)
            VALUES ('Login fallido: usuario inexistente', '127.0.0.1', 'auth')
            RETURNING id_bitacora
            """
        )
        assert cur.fetchone()[0] is not None


def test_bitacora_rechaza_update(usuarios):
    id_usuario = _crear_usuario(usuarios)
    with usuarios.cursor() as cur:
        cur.execute(
            "INSERT INTO bitacora (id_usuario, accion, modulo) "
            "VALUES (%s, 'Consulta de inventario', 'inventario')",
            (id_usuario,),
        )
        with pytest.raises(errors.RaiseException):
            cur.execute("UPDATE bitacora SET accion = 'alterado'")


def test_bitacora_rechaza_delete(usuarios):
    id_usuario = _crear_usuario(usuarios)
    with usuarios.cursor() as cur:
        cur.execute(
            "INSERT INTO bitacora (id_usuario, accion, modulo) "
            "VALUES (%s, 'Consulta RAG', 'rag_chat')",
            (id_usuario,),
        )
        with pytest.raises(errors.RaiseException):
            cur.execute("DELETE FROM bitacora")


def test_bitacora_rechaza_truncate(usuarios):
    with usuarios.cursor() as cur:
        with pytest.raises(errors.RaiseException):
            cur.execute("TRUNCATE bitacora")


def test_bitacora_no_borra_auditoria_al_eliminar_usuario(usuarios):
    with usuarios.cursor() as cur:
        cur.execute(
            """
            SELECT confdeltype FROM pg_constraint
            WHERE conname = 'fk_bitacora_usuario'
            """
        )
        fila = cur.fetchone()

    assert fila is not None, "Falta la llave foranea de bitacora hacia usuarios"
    assert fila[0] == "r", "La FK debe ser ON DELETE RESTRICT"
