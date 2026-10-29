"""Eliminacion de catalogos cargados contra la base de prueba.

Solicitud del cliente: se puede eliminar un catalogo incluso si ya fue
procesado; ademas del registro en ``archivos_subidos`` se quitan los
productos que provienen de el y el original guardado en ``UPLOADS_DIR``.
"""

import hashlib
import uuid

from app.models import inventario as inventario_model
from app.services import etl_service


def _archivo_procesado(conexion, estado: str = "ok"):
    """Inserta un archivo 'procesado' con dos productos directamente en la base."""
    ruta = f"{uuid.uuid4().hex}.xlsx"
    hash_sha256 = hashlib.sha256(ruta.encode()).hexdigest()
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO archivos_subidos
                (nombre, tipo, ruta, hash_sha256, tamano_bytes, estado,
                 filas_ok, id_usuario)
            VALUES (%s, 'xlsx', %s, %s, 1234, %s, 2, 1)
            RETURNING id_archivo
            """,
            ("Catalogo a eliminar.xlsx", ruta, hash_sha256, estado),
        )
        id_archivo = cursor.fetchone()[0]

    inventario_model.insertar_o_actualizar_productos(
        id_archivo,
        [
            {
                "codigo": f"DEL-{id_archivo}-A",
                "nombre": "Martillo de prueba",
                "precio": 10.5,
                "marca": "Fipca",
                "descripcion": None,
            },
            {
                "codigo": f"DEL-{id_archivo}-B",
                "nombre": "Tornillo de prueba",
                "precio": 0.25,
                "marca": None,
                "descripcion": None,
            },
        ],
    )
    return id_archivo, ruta


def test_elimina_catalogo_procesado_con_sus_productos_y_archivo(
    conexion_rag_limpieza,
):
    id_archivo, ruta = _archivo_procesado(conexion_rag_limpieza)

    almacen = etl_service.get_settings().uploads_dir
    almacen.mkdir(parents=True, exist_ok=True)
    (almacen / ruta).write_bytes(b"contenido original del catalogo")
    assert (almacen / ruta).exists()

    try:
        resultado = etl_service.eliminar_catalogo_completo(id_archivo)

        assert resultado is not None
        assert resultado["id_archivo"] == id_archivo
        assert resultado["nombre"] == "Catalogo a eliminar.xlsx"
        assert resultado["productos_eliminados"] == 2
        assert resultado["archivo_original_eliminado"] is True

        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM archivos_subidos WHERE id_archivo = %s", (id_archivo,))
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM productos WHERE id_archivo = %s", (id_archivo,))
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT COUNT(*) FROM productos WHERE codigo LIKE 'DEL-%'",
            )
            assert cursor.fetchone()[0] == 0
        assert not (almacen / ruta).exists()
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id_archivo = %s", (id_archivo,))
            cursor.execute("DELETE FROM archivos_subidos WHERE id_archivo = %s", (id_archivo,))


def test_producto_rehomed_a_otro_catalogo_sobrevive(conexion_rag_limpieza):
    """Un codigo reinsertado desde otro archivo queda en ese archivo."""
    id_viejo, _ = _archivo_procesado(conexion_rag_limpieza)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT id FROM productos WHERE id_archivo = %s", (id_viejo,))
            id_producto = cursor.fetchone()[0]
            cursor.execute("SELECT codigo FROM productos WHERE id = %s", (id_producto,))
            codigo = cursor.fetchone()[0]

        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO archivos_subidos
                    (nombre, tipo, estado)
                VALUES ('Archivo nuevo.xlsx', 'xlsx', 'pendiente')
                RETURNING id_archivo
                """
            )
            id_nuevo = cursor.fetchone()[0]

        inventario_model.insertar_o_actualizar_productos(
            id_nuevo,
            [{"codigo": codigo, "nombre": "Martillo rehomed", "precio": 9.99}],
        )
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT id_archivo FROM productos WHERE id = %s", (id_producto,))
            assert cursor.fetchone()[0] == id_nuevo

        resultado = etl_service.eliminar_catalogo_completo(id_viejo)
        assert resultado["productos_eliminados"] == 1

        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM productos WHERE id = %s", (id_producto,))
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "SELECT COUNT(*) FROM productos WHERE id_archivo = %s", (id_nuevo,)
            )
            assert cursor.fetchone()[0] == 1
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id_archivo = ANY(%s)", ([id_viejo, id_nuevo],))
            cursor.execute("DELETE FROM archivos_subidos WHERE id_archivo = ANY(%s)", ([id_viejo, id_nuevo],))


def test_eliminar_catalogo_inexistente_devuelve_none(conexion_rag_limpieza):
    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute("SELECT COALESCE(MAX(id_archivo), 0) FROM archivos_subidos")
        inexistente = cursor.fetchone()[0] + 5000

    assert etl_service.eliminar_catalogo_completo(inexistente) is None


def test_ruta_fuera_de_uploads_nunca_se_borra(conexion_rag_limpieza, monkeypatch):
    """Una ruta malintencionada en la base no logra borrar archivos ajenos."""
    id_archivo, _ = _archivo_procesado(conexion_rag_limpieza)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                "UPDATE archivos_subidos SET ruta = %s WHERE id_archivo = %s",
                (f"{etl_service.get_settings().uploads_dir.name}-ajeno/secreto.txt", id_archivo),
            )

        resultado = etl_service.eliminar_catalogo_completo(id_archivo)

        assert resultado["archivo_original_eliminado"] is False
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM archivos_subidos WHERE id_archivo = %s", (id_archivo,))
            assert cursor.fetchone()[0] == 0
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id_archivo = %s", (id_archivo,))
