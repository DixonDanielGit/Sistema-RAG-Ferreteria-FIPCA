"""Pruebas de la ruta de detalle comercial del buscador."""

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


def test_detalle_producto_devuelve_producto_proveedor_y_catalogo(monkeypatch):
    detalle = {
        "producto": {
            "id": 12,
            "codigo": "M-12",
            "nombre": "Manguera",
            "precio": 8.5,
            "moneda": "USD",
            "iva": 16,
            "descuentos": 0,
            "stock": 4,
        },
        "proveedor": {"id": 3, "nombre": "Proveedor Uno"},
        "catalogo": {
            "id": 6,
            "nombre": "catalogo.xlsx",
            "tipo": "xlsx",
            "fecha_de_subida": "2026-03-01T10:00:00",
            "estado": "ok",
            "filas_ok": 10,
            "filas_error": 0,
            "moneda": "USD",
        },
        "ofertas": [],
    }
    llamadas = []

    def obtener(id_producto):
        llamadas.append(id_producto)
        return detalle

    monkeypatch.setattr(
        inventario.inventario_model, "obtener_detalle_producto", obtener
    )
    monkeypatch.setattr(
        inventario, "registrar_evento", lambda *_args, **_kwargs: None
    )

    respuesta = _cliente().get("/api/v1/inventario/productos/12")

    assert respuesta.status_code == 200
    assert respuesta.json()["producto"]["codigo"] == "M-12"
    assert respuesta.json()["proveedor"]["nombre"] == "Proveedor Uno"
    assert respuesta.json()["catalogo"]["nombre"] == "catalogo.xlsx"
    assert llamadas == [12]


def test_detalle_producto_inexistente_devuelve_404(monkeypatch):
    monkeypatch.setattr(
        inventario.inventario_model, "obtener_detalle_producto", lambda _id: None
    )

    respuesta = _cliente().get("/api/v1/inventario/productos/999")

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "Producto no encontrado"


def test_detalle_producto_rechaza_ids_no_positivos():
    respuesta = _cliente().get("/api/v1/inventario/productos/0")

    assert respuesta.status_code == 422
