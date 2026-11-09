"""Pruebas unitarias de la ruta de busqueda directa del catalogo."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import usuario_actual
from app.api.v1 import inventario


def _cliente():
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")
    aplicacion.dependency_overrides[usuario_actual] = lambda: {
        "id": 9,
        "rol": "admin",
    }
    return TestClient(aplicacion)


def test_busqueda_acepta_un_caracter_y_consulta_productos_sin_archivos(
    monkeypatch,
):
    llamadas = []

    def buscar(consulta, limite, desplazamiento, ordenar_por, direccion):
        llamadas.append(
            (consulta, limite, desplazamiento, ordenar_por, direccion)
        )
        return [], 0

    monkeypatch.setattr(inventario.inventario_model, "buscar_productos_fulltext", buscar)
    monkeypatch.setattr(inventario, "registrar_evento", lambda *_args, **_kwargs: None)

    respuesta = _cliente().get(
        "/api/v1/inventario/busqueda",
        params={"consulta": "q"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "consulta": "q",
        "total": 0,
        "pagina": 1,
        "limite": inventario.LIMITE_DEFECTO_BUSQUEDA,
        "productos": [],
    }
    assert llamadas == [
        ("q", inventario.LIMITE_DEFECTO_BUSQUEDA, 0, None, "asc")
    ]


def test_busqueda_pagina_y_orden_se_aplican_en_la_consulta(monkeypatch):
    llamadas = []

    def buscar(consulta, limite, desplazamiento, ordenar_por, direccion):
        llamadas.append(
            (consulta, limite, desplazamiento, ordenar_por, direccion)
        )
        return [], 24

    monkeypatch.setattr(
        inventario.inventario_model, "buscar_productos_fulltext", buscar
    )
    monkeypatch.setattr(inventario, "registrar_evento", lambda *_args, **_kwargs: None)

    respuesta = _cliente().get(
        "/api/v1/inventario/busqueda",
        params={
            "consulta": "tornillo",
            "pagina": 3,
            "limite": 10,
            "ordenar_por": "precio",
            "direccion": "desc",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["pagina"] == 3
    assert respuesta.json()["limite"] == 10
    assert respuesta.json()["total"] == 24
    assert llamadas == [("tornillo", 10, 20, "precio", "desc")]


def test_busqueda_rechaza_columna_o_direccion_de_orden_no_permitida():
    cliente = _cliente()

    columna = cliente.get(
        "/api/v1/inventario/busqueda",
        params={"consulta": "tornillo", "ordenar_por": "id; DROP TABLE productos"},
    )
    direccion = cliente.get(
        "/api/v1/inventario/busqueda",
        params={"consulta": "tornillo", "direccion": "asc; DROP TABLE productos"},
    )

    assert columna.status_code == 422
    assert direccion.status_code == 422


def test_busqueda_sigue_rechazando_consulta_vacia_o_de_espacios():
    cliente = _cliente()

    vacia = cliente.get("/api/v1/inventario/busqueda", params={"consulta": ""})
    espacios = cliente.get("/api/v1/inventario/busqueda", params={"consulta": " "})

    assert vacia.status_code == 422
    assert espacios.status_code == 422
