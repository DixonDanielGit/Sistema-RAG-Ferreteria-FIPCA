"""Pruebas de caja negra de la ruta HTTP de eliminacion de catalogos."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.deps import requiere_admin, usuario_actual
from app.api.v1 import inventario


def _app(usuario=None, *, rechazar=False):
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")

    def autorizar():
        if rechazar:
            raise HTTPException(status_code=403, detail="Se requiere rol administrador")
        return usuario or {"id": 9, "rol": "admin"}

    aplicacion.dependency_overrides[requiere_admin] = autorizar
    aplicacion.dependency_overrides[usuario_actual] = autorizar
    return aplicacion


def test_admin_elimina_catalogo_procesado(monkeypatch):
    llamadas = []

    def eliminar(id_archivo):
        llamadas.append(id_archivo)
        return {
            "id_archivo": id_archivo,
            "nombre": "Ferreteria NVIDIA.xlsx",
            "productos_eliminados": 42,
            "archivo_original_eliminado": True,
        }

    monkeypatch.setattr(inventario.etl_service, "eliminar_catalogo_completo", eliminar)
    cliente = TestClient(_app())

    respuesta = cliente.delete("/api/v1/inventario/archivos/7")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo == {
        "id_archivo": 7,
        "nombre": "Ferreteria NVIDIA.xlsx",
        "productos_eliminados": 42,
        "archivo_original_eliminado": True,
    }
    assert llamadas == [7]


def test_eliminar_catalogo_inexistente_responde_404(monkeypatch):
    monkeypatch.setattr(
        inventario.etl_service, "eliminar_catalogo_completo", lambda _id: None
    )
    cliente = TestClient(_app())

    respuesta = cliente.delete("/api/v1/inventario/archivos/999")

    assert respuesta.status_code == 404


def test_eliminar_catalogo_requiere_administrador(monkeypatch):
    llamada = False

    def eliminar(*_):
        nonlocal llamada
        llamada = True
        return None

    monkeypatch.setattr(inventario.etl_service, "eliminar_catalogo_completo", eliminar)
    cliente = TestClient(_app(rechazar=True))

    respuesta = cliente.delete("/api/v1/inventario/archivos/5")

    assert respuesta.status_code == 403
    assert not llamada


def test_ids_negativos_no_se_procesan(monkeypatch):
    def eliminar(_id):
        raise AssertionError("No debe consultarse el modelo con ids sin sentido")

    monkeypatch.setattr(inventario.etl_service, "eliminar_catalogo_completo", eliminar)
    cliente = TestClient(_app())

    assert cliente.delete("/api/v1/inventario/archivos/0").status_code == 422
