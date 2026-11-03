"""Pruebas del modelo de consulta del asistente (migracion 7_0).

Corren sobre la copia desechable ``ferreteria_rag_test``, que recibe la
migracion ``7_0`` desde ``tests/conftest.py``. No tocan la base de desarrollo.

Se comprueba que:
- existan las tablas y columnas que sostienen las tres preguntas del cliente;
- las reglas de negocio (precio, reorden, cantidades) se impongan en la base;
- las consultas objetivo devuelvan el resultado esperado con datos reales.
"""

from __future__ import annotations

import uuid

import pytest

from app.models import inventario as inventario_model

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import errors  # noqa: E402  (depende del importorskip)

TABLAS = {
    "producto_proveedor",
    "historial_precios",
    "compras",
    "detalle_compra",
    "evaluacion_proveedor",
    "stock_movimientos",
    "configuracion_stock",
    "producto_alias",
    "tasa_cambio",
}

COLUMNAS_PRODUCTOS = {
    "codigo_interno",
    "moneda",
    "unidad_medida",
    "presentacion",
    "punto_reorden",
    "ubicacion",
    "activo",
    "modelo_embedding",
    "vectorizado_en",
}

COLUMNAS_PROVEEDORES = {
    "rif",
    "telefono",
    "correo",
    "vendedor",
    "telefono_vendedor",
    "correo_vendedor",
    "moneda",
    "plazo_entrega_dias",
    "activo",
    "actualizado_en",
}

COLUMNAS_ARCHIVOS = {
    "id_proveedor",
    "vendedor_nombre",
    "vendedor_telefono",
    "vendedor_correo",
    "moneda",
    "nota_proveedor",
}

COLUMNAS_OFERTAS = {
    "iva",
    "iva_incluido",
    "descuento",
    "cantidad_disponible_proveedor",
    "politica_ventas",
}


def _columnas(conexion, tabla):
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = %s
            """,
            (tabla,),
        )
        return {fila[0] for fila in cursor.fetchall()}


def _crear_producto(conexion, sufijo, *, stock=0):
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO productos (codigo, nombre, precio, stock)
            VALUES (%s, 'Producto de prueba 7.0', 10.00, %s)
            RETURNING id
            """,
            (f"T7-{sufijo}", stock),
        )
        return cursor.fetchone()[0]


def _crear_proveedor(conexion, sufijo, *, plazo=None):
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO proveedores (nombre, plazo_entrega_dias)
            VALUES (%s, %s)
            RETURNING id_proveedores
            """,
            (f"Proveedor {sufijo}", plazo),
        )
        return cursor.fetchone()[0]


def _limpiar(conexion, *, productos=(), proveedores=()):
    with conexion.cursor() as cursor:
        if productos:
            cursor.execute("DELETE FROM productos WHERE id = ANY(%s)", (list(productos),))
        if proveedores:
            cursor.execute(
                "DELETE FROM proveedores WHERE id_proveedores = ANY(%s)",
                (list(proveedores),),
            )


# ---------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------

def test_existen_las_tablas_del_modelo_de_consulta(conexion_rag_limpieza):
    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        tablas = {fila[0] for fila in cursor.fetchall()}

    assert TABLAS <= tablas


def test_columnas_nuevas_de_productos_y_proveedores(conexion_rag_limpieza):
    assert COLUMNAS_PRODUCTOS <= _columnas(conexion_rag_limpieza, "productos")
    assert COLUMNAS_PROVEEDORES <= _columnas(conexion_rag_limpieza, "proveedores")
    assert COLUMNAS_ARCHIVOS <= _columnas(conexion_rag_limpieza, "archivos_subidos")
    assert COLUMNAS_OFERTAS <= _columnas(
        conexion_rag_limpieza, "producto_proveedor"
    )


def test_configuracion_stock_tiene_una_sola_fila(conexion_rag_limpieza):
    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute(
            """
            SELECT stock_minimo_global, dias_cobertura_alerta
              FROM configuracion_stock
             WHERE id = 1
            """
        )
        fila = cursor.fetchone()

    assert fila is not None
    assert fila[0] >= 0
    assert fila[1] > 0

    with conexion_rag_limpieza.cursor() as cursor:
        with pytest.raises(errors.CheckViolation):
            cursor.execute("INSERT INTO configuracion_stock (id) VALUES (2)")


# ---------------------------------------------------------------------
# Reglas de negocio
# ---------------------------------------------------------------------

def test_punto_reorden_negativo_es_rechazado(conexion_rag_limpieza):
    with conexion_rag_limpieza.cursor() as cursor:
        with pytest.raises(errors.CheckViolation):
            cursor.execute(
                """
                INSERT INTO productos (nombre, precio, punto_reorden)
                VALUES ('Reorden invalido', 5.00, -1)
                """
            )


def test_precio_de_oferta_no_puede_ser_negativo(conexion_rag_limpieza):
    sufijo = uuid.uuid4().hex[:10]
    id_producto = _crear_producto(conexion_rag_limpieza, sufijo)
    id_proveedor = _crear_proveedor(conexion_rag_limpieza, sufijo)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            with pytest.raises(errors.CheckViolation):
                cursor.execute(
                    """
                    INSERT INTO producto_proveedor
                        (id_producto, id_proveedor, codigo_proveedor, precio)
                    VALUES (%s, %s, %s, -0.01)
                    """,
                    (id_producto, id_proveedor, f"COD-{sufijo}"),
                )
    finally:
        _limpiar(
            conexion_rag_limpieza,
            productos=(id_producto,),
            proveedores=(id_proveedor,),
        )


def test_oferta_admite_descuento_opcional_y_disponibilidad_de_proveedor(
    conexion_rag_limpieza,
):
    sufijo = uuid.uuid4().hex[:10]
    id_producto = _crear_producto(conexion_rag_limpieza, sufijo)
    id_proveedor = _crear_proveedor(conexion_rag_limpieza, sufijo)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO producto_proveedor
                    (id_producto, id_proveedor, codigo_proveedor, precio,
                     cantidad_disponible_proveedor, politica_ventas)
                VALUES (%s, %s, %s, 10.61, 43, 'Descuento hasta manana')
                RETURNING iva, iva_incluido, descuento,
                          cantidad_disponible_proveedor, politica_ventas
                """,
                (id_producto, id_proveedor, f"SKU-{sufijo}"),
            )
            iva, incluido, descuento, cantidad, politica = cursor.fetchone()
            cursor.execute(
                "SELECT stock FROM productos WHERE id = %s",
                (id_producto,),
            )
            stock = cursor.fetchone()[0]

        assert float(iva) == 0
        assert incluido is None
        assert descuento is None
        assert cantidad == 43
        assert politica == "Descuento hasta manana"
        assert stock == 0
    finally:
        _limpiar(
            conexion_rag_limpieza,
            productos=(id_producto,),
            proveedores=(id_proveedor,),
        )


def test_ingesta_persiste_proveedor_vendedor_y_oferta_separada_del_stock(
    conexion_rag_limpieza,
):
    sufijo = uuid.uuid4().hex[:10]
    nombre_proveedor = f"Proveedor carga {sufijo}"
    codigo = f"CAT-{sufijo}"
    archivo = inventario_model.crear_archivo(
        nombre="cotizacion.pdf",
        tipo="pdf",
        ruta=f"{sufijo}.pdf",
        hash_sha256=sufijo.ljust(64, "0"),
        tamano_bytes=123,
        id_usuario=1,
        metadatos={
            "proveedor": nombre_proveedor,
            "vendedor": "Vendedora de prueba",
            "telefono_vendedor": "0212-555-0101",
            "correo_vendedor": "ventas@example.com",
            "moneda": "VES",
            "nota_proveedor": "Descuento hasta manana",
        },
    )
    id_archivo = archivo["id_archivo"]

    try:
        producto = {
            "codigo": codigo,
            "nombre": "Abrazadera de prueba",
            "precio": 10.61,
            "marca": "Imp",
            "cantidad_disponible_proveedor": 43,
            "politica_ventas": "Oferta de prueba",
        }
        inventario_model.insertar_o_actualizar_productos(id_archivo, [producto])
        assert inventario_model.insertar_o_actualizar_ofertas(
            id_archivo, [producto]
        ) == 1

        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.nombre, p.vendedor, a.vendedor_nombre, a.moneda,
                       a.nota_proveedor, o.precio, o.moneda, o.iva,
                       o.descuento, o.cantidad_disponible_proveedor,
                       o.politica_ventas, pr.stock,
                       (SELECT COUNT(*) FROM historial_precios h
                         WHERE h.id_archivo = a.id_archivo)
                  FROM archivos_subidos a
                  JOIN proveedores p ON p.id_proveedores = a.id_proveedor
                  JOIN producto_proveedor o ON o.id_archivo = a.id_archivo
                  JOIN productos pr ON pr.id = o.id_producto
                 WHERE a.id_archivo = %s
                """,
                (id_archivo,),
            )
            resultado = cursor.fetchone()

        assert resultado is not None
        assert resultado[0] == nombre_proveedor
        assert resultado[1] == "Vendedora de prueba"
        assert resultado[2] == "Vendedora de prueba"
        assert resultado[3:5] == ("VES", "Descuento hasta manana")
        assert float(resultado[5]) == 10.61
        assert resultado[6:9] == ("VES", 0, None)
        assert resultado[9:12] == (43, "Oferta de prueba", 0)
        assert resultado[12] == 1
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE codigo = %s", (codigo,))
            cursor.execute(
                "DELETE FROM archivos_subidos WHERE id_archivo = %s",
                (id_archivo,),
            )
            cursor.execute(
                "DELETE FROM proveedores WHERE LOWER(nombre) = LOWER(%s)",
                (nombre_proveedor,),
            )


def test_ingesta_revierte_productos_si_falla_una_oferta(conexion_rag_limpieza):
    sufijo = uuid.uuid4().hex[:10]
    nombre_proveedor = f"Proveedor rollback {sufijo}"
    codigo = f"ROLLBACK-{sufijo}"
    archivo = inventario_model.crear_archivo(
        nombre="cotizacion.pdf",
        tipo="pdf",
        ruta=f"{sufijo}.pdf",
        hash_sha256=sufijo.ljust(64, "0"),
        tamano_bytes=123,
        id_usuario=1,
        metadatos={"proveedor": nombre_proveedor, "vendedor": "Vendedora"},
    )
    try:
        with pytest.raises(errors.CheckViolation):
            inventario_model.insertar_catalogo_completo(
                archivo["id_archivo"],
                [
                    {
                        "codigo": codigo,
                        "nombre": "Producto de rollback",
                        "precio": 10.00,
                        "descuento_oferta": -1,
                    }
                ],
                guardar_ofertas=True,
            )

        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM productos WHERE codigo = %s", (codigo,))
            assert cursor.fetchone()[0] == 0
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                "DELETE FROM archivos_subidos WHERE id_archivo = %s",
                (archivo["id_archivo"],),
            )
            cursor.execute(
                "DELETE FROM proveedores WHERE LOWER(nombre) = LOWER(%s)",
                (nombre_proveedor,),
            )


def test_cantidad_recibida_no_supera_la_solicitada(conexion_rag_limpieza):
    sufijo = uuid.uuid4().hex[:10]
    id_producto = _crear_producto(conexion_rag_limpieza, sufijo)
    id_proveedor = _crear_proveedor(conexion_rag_limpieza, sufijo)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO compras (id_proveedor, estado)
                VALUES (%s, 'recibida')
                RETURNING id_compra
                """,
                (id_proveedor,),
            )
            id_compra = cursor.fetchone()[0]

            with pytest.raises(errors.CheckViolation):
                cursor.execute(
                    """
                    INSERT INTO detalle_compra
                        (id_compra, id_producto, cantidad_solicitada,
                         cantidad_recibida, precio_unitario)
                    VALUES (%s, %s, 10, 11, 5.00)
                    """,
                    (id_compra, id_producto),
                )
    finally:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM compras WHERE id_proveedor = %s", (id_proveedor,))
        _limpiar(
            conexion_rag_limpieza,
            productos=(id_producto,),
            proveedores=(id_proveedor,),
        )


# ---------------------------------------------------------------------
# Consultas objetivo
# ---------------------------------------------------------------------

def test_consulta_del_proveedor_mas_barato_y_su_plazo(conexion_rag_limpieza):
    """P1: el precio mas bajo y los dias de entrega salen de la misma fila."""
    sufijo = uuid.uuid4().hex[:10]
    id_producto = _crear_producto(conexion_rag_limpieza, sufijo)
    id_caro = _crear_proveedor(conexion_rag_limpieza, f"caro-{sufijo}", plazo=3)
    id_barato = _crear_proveedor(conexion_rag_limpieza, f"barato-{sufijo}", plazo=7)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO producto_proveedor
                    (id_producto, id_proveedor, codigo_proveedor, precio,
                     plazo_entrega_dias, disponible)
                VALUES (%s, %s, %s, 9.90, 3, TRUE),
                       (%s, %s, %s, 7.90, 7, TRUE)
                """,
                (
                    id_producto, id_caro, f"A-{sufijo}",
                    id_producto, id_barato, f"B-{sufijo}",
                ),
            )

            cursor.execute(
                """
                SELECT pr.nombre, o.precio,
                       COALESCE(o.plazo_entrega_dias, pr.plazo_entrega_dias)
                  FROM producto_proveedor AS o
                  JOIN productos AS p ON p.id = o.id_producto
                  JOIN proveedores AS pr ON pr.id_proveedores = o.id_proveedor
                 WHERE p.id = %s AND o.disponible
                 ORDER BY o.precio ASC
                """,
                (id_producto,),
            )
            resultados = cursor.fetchall()

        assert [fila[0] for fila in resultados] == [
            f"Proveedor barato-{sufijo}",
            f"Proveedor caro-{sufijo}",
        ]
        assert float(resultados[0][1]) == 7.90
        assert resultados[0][2] == 7, "El plazo debe viajar con el precio"
        assert resultados[1][2] == 3, "El mas caro entrega antes: hay que decirlo"
    finally:
        _limpiar(
            conexion_rag_limpieza,
            productos=(id_producto,),
            proveedores=(id_caro, id_barato),
        )


def test_consulta_de_cobertura_de_stock(conexion_rag_limpieza):
    """P3: el consumo de los ultimos 30 dias define la cobertura en dias."""
    sufijo = uuid.uuid4().hex[:10]
    id_producto = _crear_producto(conexion_rag_limpieza, sufijo, stock=12)

    try:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stock_movimientos (id_producto, tipo, cantidad, ocurrido_en)
                VALUES
                    (%s, 'salida', 20, NOW() - INTERVAL '25 days'),
                    (%s, 'salida', 20, NOW() - INTERVAL '18 days'),
                    (%s, 'salida', 20, NOW() - INTERVAL '11 days'),
                    (%s, 'salida', 20, NOW() - INTERVAL '4 days')
                """,
                (id_producto, id_producto, id_producto, id_producto),
            )

            cursor.execute(
                """
                WITH consumo AS (
                    SELECT id_producto,
                           SUM(ABS(cantidad)) FILTER (WHERE tipo = 'salida') AS unidades
                      FROM stock_movimientos
                     WHERE id_producto = %s
                       AND ocurrido_en >= NOW() - INTERVAL '30 days'
                     GROUP BY id_producto
                )
                SELECT p.stock,
                       ROUND(p.stock / (c.unidades / 30.0), 1)
                  FROM productos AS p
                  JOIN consumo AS c ON c.id_producto = p.id
                 WHERE p.id = %s
                """,
                (id_producto, id_producto),
            )
            stock, cobertura = cursor.fetchone()

        assert stock == 12
        assert float(cobertura) == 4.5
    finally:
        _limpiar(conexion_rag_limpieza, productos=(id_producto,))
