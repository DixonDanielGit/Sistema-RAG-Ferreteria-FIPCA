"""Pruebas de la consulta parametrizada de la ficha comercial."""

from datetime import date, datetime

from app.models import inventario


def test_obtener_detalle_producto_compone_origen_proveedor_y_ofertas(monkeypatch):
    fila = {
        "id": 7,
        "codigo": "COD-7",
        "codigo_interno": None,
        "nombre": "Producto",
        "marca": "Marca",
        "categoria": "Herramientas",
        "descripcion": "Descripción",
        "unidad_medida": "unidad",
        "presentacion": "Caja",
        "precio": 12.5,
        "moneda": "USD",
        "iva": 16,
        "descuentos": 0,
        "stock": 2,
        "punto_reorden": 1,
        "ubicacion": "Pasillo 1",
        "actualizado_en": datetime(2026, 3, 1, 10),
        "proveedor_id": 3,
        "proveedor_nombre": "Proveedor Uno",
        "proveedor_rif": "J-123",
        "proveedor_direccion": "Caracas",
        "proveedor_telefono": None,
        "proveedor_correo": None,
        "proveedor_vendedor": "Vendedor",
        "proveedor_telefono_vendedor": None,
        "proveedor_correo_vendedor": None,
        "proveedor_moneda": "USD",
        "catalogo_id": 11,
        "catalogo_nombre": "catalogo.xlsx",
        "catalogo_tipo": "xlsx",
        "catalogo_fecha": datetime(2026, 3, 1, 9),
        "catalogo_estado": "ok",
        "catalogo_filas_ok": 5,
        "catalogo_filas_error": 0,
        "catalogo_moneda": "USD",
        "catalogo_nota_proveedor": None,
        "catalogo_vendedor": "Vendedor",
        "catalogo_telefono_vendedor": None,
        "catalogo_correo_vendedor": None,
    }
    oferta = {
        "id": 18,
        "proveedor": "Proveedor Dos",
        "codigo_proveedor": "P-7",
        "precio": 10,
        "moneda": "USD",
        "iva": 16,
        "iva_incluido": False,
        "descuento": 0,
        "cantidad_disponible_proveedor": 8,
        "politica_ventas": None,
        "plazo_entrega_dias": 2,
        "cantidad_minima": 1,
        "disponible": True,
        "fecha_cotizacion": date(2026, 3, 1),
        "catalogo": "oferta.xlsx",
    }
    consultas = []

    def consultar_uno(sql, parametros, *, rag=False):
        consultas.append((sql, parametros, rag))
        return fila

    def consultar_todos(sql, parametros, *, rag=False):
        consultas.append((sql, parametros, rag))
        return [oferta]

    monkeypatch.setattr(inventario, "consultar_uno", consultar_uno)
    monkeypatch.setattr(inventario, "consultar_todos", consultar_todos)

    detalle = inventario.obtener_detalle_producto(7)

    assert detalle["producto"]["codigo"] == "COD-7"
    assert detalle["proveedor"]["nombre"] == "Proveedor Uno"
    assert detalle["catalogo"]["nombre"] == "catalogo.xlsx"
    assert detalle["ofertas"] == [oferta]
    assert [consulta[1] for consulta in consultas] == [(7,), (7,)]
    assert all(consulta[2] is True for consulta in consultas)
    assert all("%s" in consulta[0] for consulta in consultas)


def test_obtener_detalle_producto_inexistente_no_consulta_ofertas(monkeypatch):
    monkeypatch.setattr(inventario, "consultar_uno", lambda *_args, **_kwargs: None)
    consultas_ofertas = []
    monkeypatch.setattr(
        inventario,
        "consultar_todos",
        lambda *args, **kwargs: consultas_ofertas.append((args, kwargs)),
    )

    assert inventario.obtener_detalle_producto(999) is None
    assert consultas_ofertas == []
