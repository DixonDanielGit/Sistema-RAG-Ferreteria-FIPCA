"""Pruebas de las rutas para observaciones comerciales."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import inventario as rutas_inventario


def cliente_con_sesion(monkeypatch):
    aplicacion = FastAPI()
    aplicacion.include_router(rutas_inventario.router)
    aplicacion.dependency_overrides[rutas_inventario.usuario_actual] = lambda: {
        "id": 29
    }
    eventos = []
    monkeypatch.setattr(
        rutas_inventario,
        "registrar_evento",
        lambda _request, accion, *, id_usuario: eventos.append(
            (accion, id_usuario)
        ),
    )
    return TestClient(aplicacion), eventos


def test_actualiza_observacion_de_producto_y_registra_usuario(monkeypatch):
    cliente, eventos = cliente_con_sesion(monkeypatch)
    monkeypatch.setattr(
        rutas_inventario.inventario_model,
        "actualizar_observacion_producto",
        lambda id_producto, observacion: {
            "observacion": observacion,
            "id": id_producto,
        },
    )

    respuesta = cliente.patch(
        "/inventario/productos/12/observacion",
        json={"observacion": "Descuento frecuente"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"observacion": "Descuento frecuente"}
    assert eventos == [
        ("actualizacion de observacion comercial de producto: 12", 29)
    ]


def test_elimina_observacion_de_producto_sin_cuerpo(monkeypatch):
    cliente, eventos = cliente_con_sesion(monkeypatch)
    monkeypatch.setattr(
        rutas_inventario.inventario_model,
        "eliminar_observacion_producto",
        lambda id_producto: {"id": id_producto},
    )

    respuesta = cliente.delete("/inventario/productos/12/observacion")

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert eventos == [
        ("eliminacion de observacion comercial de producto: 12", 29)
    ]


def test_limpia_observacion_compartida_del_catalogo(monkeypatch):
    cliente, eventos = cliente_con_sesion(monkeypatch)
    valores_guardados = []

    def actualizar(id_archivo, observacion):
        valores_guardados.append((id_archivo, observacion))
        return {"observacion": observacion}

    monkeypatch.setattr(
        rutas_inventario.inventario_model,
        "actualizar_observacion_catalogo",
        actualizar,
    )

    respuesta = cliente.patch(
        "/inventario/catalogos/5/observacion",
        json={"observacion": None},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"observacion": None}
    assert valores_guardados == [(5, None)]
    assert eventos == [
        ("actualizacion de observacion comercial de catalogo: 5", 29)
    ]


def test_no_acepta_observacion_de_producto_vacia(monkeypatch):
    cliente, _ = cliente_con_sesion(monkeypatch)

    respuesta = cliente.patch(
        "/inventario/productos/12/observacion",
        json={"observacion": "   "},
    )

    assert respuesta.status_code == 422
