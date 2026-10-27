import uuid
from pathlib import Path

from app.models import inventario as inventario_model


def test_esquema_vectorial_384_y_busqueda_coseno(
    conexion_rag_limpieza,
):
    raiz = Path(__file__).resolve().parents[2]
    migracion = (raiz / "scripts" / "migracion_4_0.sql").read_text(
        encoding="utf-8"
    )
    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute(migracion)

    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
              FROM pg_attribute AS a
             WHERE a.attrelid = 'productos'::regclass
               AND a.attname = 'descripcion_vectorial'
               AND NOT a.attisdropped
            """
        )
        assert cursor.fetchone()[0] == "vector(384)"

        codigo = f"TEST-VECTOR-{uuid.uuid4().hex[:12]}"
        cursor.execute(
            """
            INSERT INTO productos (codigo, nombre, precio)
            VALUES (%s, 'Taladro de prueba', 1.00)
            RETURNING id
            """,
            (codigo,),
        )
        id_producto = cursor.fetchone()[0]

    try:
        vector = [0.0] * 384
        vector[0] = 1.0
        assert inventario_model.guardar_embeddings([(id_producto, vector)]) == 1
        assert inventario_model.guardar_embeddings([(id_producto, vector)]) == 0

        resultados = inventario_model.buscar_productos_por_vector(vector, 5)

        resultado = next(item for item in resultados if item["codigo"] == codigo)
        assert abs(float(resultado["similitud"]) - 1.0) < 1e-6
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id = %s", (id_producto,))
