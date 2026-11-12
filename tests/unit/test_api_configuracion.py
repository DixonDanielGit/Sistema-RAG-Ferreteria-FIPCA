"""Pruebas unitarias del endpoint de diagnostico tecnico."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1 import auth


def _cliente(monkeypatch):
    aplicacion = FastAPI()
    aplicacion.include_router(auth.router, prefix="/api/v1")
    # `requiere_permiso` es una fabrica: se resuelve la capacidad sobre la
    # cuenta que entrega `usuario_actual`, que es la dependencia real.
    aplicacion.dependency_overrides[deps.usuario_actual] = lambda: {
        "id": 1,
        "rol": "admin",
        "permisos": ["configuracion:diagnostico"],
    }
    monkeypatch.setattr(auth, "consultar_uno", lambda *_a, **_k: {"ok": 1})
    return TestClient(aplicacion)


def test_diagnostico_informa_las_bases_sin_servicios_de_ia(monkeypatch):
    datos = _cliente(monkeypatch).get(
        "/api/v1/auth/configuracion/admin"
    ).json()

    assert datos["bases"] == {
        "ferreteria_rag": "operativa",
        "ferreteria_usuarios": "operativa",
    }
    assert "openrouter" not in datos
    assert "llm" not in datos


def test_diagnostico_lista_los_formatos_locales_del_etl(monkeypatch):
    from app.services import etl_service

    datos = _cliente(monkeypatch).get(
        "/api/v1/auth/configuracion/admin"
    ).json()

    assert datos["ingesta"]["formatos"] == sorted(
        etl_service.EXTENSIONES_PERMITIDAS
    )
    assert ".md" not in datos["ingesta"]["formatos"]
    assert datos["ingesta"]["max_filas_archivo"] == etl_service.MAX_FILAS_ARCHIVO
    assert (
        datos["ingesta"]["max_lineas_texto_archivo"]
        == etl_service.MAX_LINEAS_TEXTO_ARCHIVO
    )
    assert datos["ingesta"]["max_paginas_pdf"] == etl_service.MAX_PAGINAS_PDF
    assert datos["ingesta"]["max_paginas_docx"] == etl_service.MAX_PAGINAS_DOCX
