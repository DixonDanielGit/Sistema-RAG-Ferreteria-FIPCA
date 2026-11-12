"""Pruebas del endpoint de extraccion en memoria (buscador local, sin persistir).

El endpoint existe para verificar que las librerias locales leen bien los
catalogos, asi que estas pruebas exigen dos cosas: que devuelva los productos
extraidos y que no toque la base de datos ni escriba el original en disco.
"""

from __future__ import annotations

import io

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.deps import usuario_actual
from app.api.v1 import inventario
from app.services import etl_service

FILA_TXT = "Codigo;Nombre;Precio\nSKU-9;Llave inglesa;4,50\n"


def _cliente():
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")
    aplicacion.dependency_overrides[usuario_actual] = lambda: {
        "id": 9,
        "rol": "ventas",
        "permisos": [],
    }
    return TestClient(aplicacion)


def _bytes_excel(filas):
    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_extrae_productos_sin_guardar_nada(monkeypatch, tmp_path):
    def prohibir(*_args, **_kwargs):
        raise AssertionError("la extraccion en memoria no debe tocar la base")

    monkeypatch.setattr(inventario.inventario_model, "crear_archivo", prohibir)
    monkeypatch.setattr(
        inventario.inventario_model, "insertar_catalogo_completo", prohibir
    )
    monkeypatch.setattr(
        inventario.inventario_model, "actualizar_estado_archivo", prohibir
    )
    monkeypatch.setattr(etl_service, "_directorio_cargas_seguro", lambda: tmp_path)
    contenido = _bytes_excel(
        [
            ["Codigo", "Nombre", "Precio", "Marca"],
            ["SKU-01", "Martillo", 12.5, "FIPCA"],
            ["SKU-02", "Destornillador", 7.25, None],
        ]
    )

    respuesta = _cliente().post(
        "/api/v1/inventario/extraccion-prueba",
        files=[
            ("archivos", ("catalogo.xlsx", contenido, "application/vnd.ms-excel"))
        ],
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["persistido"] is False
    assert cuerpo["total_archivos"] == 1
    assert cuerpo["archivos_ok"] == 1
    assert cuerpo["productos_extraidos"] == 2

    resultado = cuerpo["resultados"][0]
    assert resultado["estado"] == "ok"
    assert resultado["filas_ok"] == 2
    assert resultado["nombre"] == "catalogo.xlsx"
    assert resultado["tipo"] == "xlsx"
    assert [producto["codigo"] for producto in resultado["productos"]] == [
        "SKU-01",
        "SKU-02",
    ]
    assert resultado["productos"][0] == {
        "codigo": "SKU-01",
        "nombre": "Martillo",
        "marca": "FIPCA",
        "precio": 12.5,
        "descuentos": 0.0,
        "descripcion": None,
        "descuento_oferta": None,
        "cantidad_disponible_proveedor": None,
        "politica_ventas": None,
        "proveedor": None,
        "telefono": None,
        "correo": None,
        "moneda": None,
        "iva_oferta": None,
        "iva_incluido": None,
    }
    # Una columna que el archivo no trae se devuelve en null, nunca inventada.
    assert resultado["productos"][1]["marca"] is None
    assert list(tmp_path.iterdir()) == []


def test_devuelve_null_en_columnas_ausentes():
    resultado = etl_service.extraer_catalogo_en_memoria(
        "lista.txt", FILA_TXT.encode()
    )

    assert resultado["estado"] == "ok"
    assert resultado["filas_ok"] == 1
    producto = resultado["productos"][0]
    assert producto["codigo"] == "SKU-9"
    assert producto["nombre"] == "Llave inglesa"
    assert producto["precio"] == 4.5
    assert producto["marca"] is None
    assert producto["descripcion"] is None


def test_formato_no_permitido_se_rechaza_sin_romper_el_lote():
    resultado = etl_service.extraer_catalogo_en_memoria("precios.csv", b"a,b,c\n")

    assert resultado["estado"] == "rechazado"
    assert resultado["productos"] == []
    assert "Formato no permitido" in resultado["detalle"]


def test_archivo_ambiguo_pide_seleccion_de_precio():
    contenido = _bytes_excel(
        [
            ["Codigo", "Nombre", "Precio lista", "Precio oferta"],
            ["SKU-1", "Alicate", 10, 8],
        ]
    )

    respuesta = _cliente().post(
        "/api/v1/inventario/extraccion-prueba",
        files=[("archivos", ("doble.xlsx", contenido, "application/vnd.ms-excel"))],
    )

    assert respuesta.status_code == 200
    resultado = respuesta.json()["resultados"][0]
    assert resultado["estado"] == "pendiente"
    assert resultado["seleccion_pendiente"] is True
    assert resultado["productos"] == []
    assert {opcion["columna"] for opcion in resultado["opciones_precio"]} == {
        "Precio lista",
        "Precio oferta",
    }

    confirmada = _cliente().post(
        "/api/v1/inventario/extraccion-prueba",
        files=[("archivos", ("doble.xlsx", contenido, "application/vnd.ms-excel"))],
        data={"selecciones_precio": '{"0": 3}'},
    )
    assert confirmada.status_code == 200
    elegido = confirmada.json()["resultados"][0]["productos"][0]
    assert elegido["precio"] == 8.0


def test_seleccion_de_precio_invalida_devuelve_400():
    respuesta = _cliente().post(
        "/api/v1/inventario/extraccion-prueba",
        files=[("archivos", ("lista.txt", FILA_TXT.encode(), "text/plain"))],
        data={"selecciones_precio": "no es json"},
    )

    assert respuesta.status_code == 400
    assert "seleccion de precios" in respuesta.json()["detail"].lower()


def test_lote_vacio_o_demasiado_grande_devuelve_400():
    cliente = _cliente()

    assert cliente.post(
        "/api/v1/inventario/extraccion-prueba", files=[]
    ).status_code == 400

    muchos = [
        ("archivos", (f"catalogo-{indice}.txt", FILA_TXT.encode(), "text/plain"))
        for indice in range(etl_service.MAX_ARCHIVOS_INGESTA + 1)
    ]
    assert cliente.post(
        "/api/v1/inventario/extraccion-prueba", files=muchos
    ).status_code == 400
