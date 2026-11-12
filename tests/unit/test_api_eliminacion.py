"""Pruebas de caja negra de la ruta HTTP de eliminacion de catalogos."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import usuario_actual
from app.api.v1 import inventario

# La eliminacion se autoriza por capacidad, no por rol fijo (modelo de 6_0).
PERMISOS_ADMIN = ("catalogos:ingestar", "catalogos:eliminar")


def _app(usuario=None):
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")

    def autorizar():
        return usuario or {"id": 9, "rol": "admin", "permisos": list(PERMISOS_ADMIN)}

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


def test_eliminar_catalogo_exige_la_capacidad_de_eliminacion(monkeypatch):
    llamada = False

    def eliminar(*_):
        nonlocal llamada
        llamada = True
        return None

    monkeypatch.setattr(inventario.etl_service, "eliminar_catalogo_completo", eliminar)
    # Puede ingerir catalogos, pero no eliminarlos.
    cliente = TestClient(
        _app(usuario={"id": 10, "rol": "ventas", "permisos": ["catalogos:ingestar"]})
    )

    respuesta = cliente.delete("/api/v1/inventario/archivos/5")

    assert respuesta.status_code == 403
    assert "permiso" in respuesta.json()["detail"]
    assert not llamada


def test_ids_negativos_no_se_procesan(monkeypatch):
    def eliminar(_id):
        raise AssertionError("No debe consultarse el modelo con ids sin sentido")

    monkeypatch.setattr(inventario.etl_service, "eliminar_catalogo_completo", eliminar)
    cliente = TestClient(_app())

    assert cliente.delete("/api/v1/inventario/archivos/0").status_code == 422


def test_admin_elimina_catalogos_seleccionados_y_reporta_ausentes(monkeypatch):
    llamadas = []

    def eliminar(ids_archivos):
        llamadas.append(ids_archivos)
        return {
            "eliminados": [
                {
                    "id_archivo": 7,
                    "nombre": "Catalogo A.xlsx",
                    "productos_eliminados": 3,
                    "archivo_original_eliminado": True,
                },
                {
                    "id_archivo": 9,
                    "nombre": "Catalogo C.txt",
                    "productos_eliminados": 0,
                    "archivo_original_eliminado": False,
                },
            ],
            "ids_no_encontrados": [8],
        }

    monkeypatch.setattr(
        inventario.etl_service, "eliminar_catalogos_completos", eliminar
    )
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/archivos/eliminacion-multiple",
        json={"ids_archivos": [7, 8, 9]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "eliminados": [
            {
                "id_archivo": 7,
                "nombre": "Catalogo A.xlsx",
                "productos_eliminados": 3,
                "archivo_original_eliminado": True,
            },
            {
                "id_archivo": 9,
                "nombre": "Catalogo C.txt",
                "productos_eliminados": 0,
                "archivo_original_eliminado": False,
            },
        ],
        "ids_no_encontrados": [8],
    }
    assert llamadas == [[7, 8, 9]]


def test_eliminar_catalogos_exige_la_capacidad_de_eliminacion(monkeypatch):
    llamada = False

    def eliminar(*_):
        nonlocal llamada
        llamada = True
        return {"eliminados": [], "ids_no_encontrados": []}

    monkeypatch.setattr(
        inventario.etl_service, "eliminar_catalogos_completos", eliminar
    )
    cliente = TestClient(
        _app(usuario={"id": 10, "rol": "ventas", "permisos": ["catalogos:ingestar"]})
    )

    respuesta = cliente.post(
        "/api/v1/inventario/archivos/eliminacion-multiple",
        json={"ids_archivos": [3, 5]},
    )

    assert respuesta.status_code == 403
    assert not llamada


def test_eliminar_catalogos_valida_minimo_ids_positivos_y_sin_duplicados(
    monkeypatch,
):
    def eliminar(*_):
        raise AssertionError("Los IDs invalidos no deben llegar al servicio")

    monkeypatch.setattr(
        inventario.etl_service, "eliminar_catalogos_completos", eliminar
    )
    cliente = TestClient(_app())
    ruta = "/api/v1/inventario/archivos/eliminacion-multiple"

    assert cliente.post(ruta, json={"ids_archivos": [1]}).status_code == 422
    assert cliente.post(ruta, json={"ids_archivos": [1, 1]}).status_code == 422
    assert cliente.post(ruta, json={"ids_archivos": [0, 2]}).status_code == 422
