"""Pruebas unitarias del endpoint de diagnostico tecnico."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1 import auth
from app.config import Settings
from app.services import markdown_transform_service


def _cliente(monkeypatch, config: Settings):
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
    monkeypatch.setattr(auth, "get_settings", lambda: config)
    return TestClient(aplicacion)


def test_diagnotico_informa_el_modelo_cargado_sin_revelar_la_clave(monkeypatch):
    config = Settings(
        openrouter_api_key="sk-or-v1-secreta",
        openrouter_model="qwen/qwen3.8-flash",
        openrouter_max_tokens=32768,
        openrouter_timeout_segundos=180,
    )

    datos = _cliente(monkeypatch, config).get(
        "/api/v1/auth/configuracion/admin"
    ).json()

    assert datos["openrouter"] == {
        "configurado": True,
        "modelo": "qwen/qwen3.8-flash",
        "max_tokens": 32768,
        "caracteres_por_lote": markdown_transform_service.MAX_CARACTERES_POR_LOTE,
        "timeout_segundos": 180,
    }
    assert "sk-or-v1-secreta" not in str(datos)


def test_diagnotico_marca_openrouter_sin_configurar(monkeypatch):
    """Sin clave el ETL usa los lectores locales: se reporta, no se oculta."""
    config = Settings(openrouter_api_key="", openrouter_model="")
    datos = _cliente(monkeypatch, config).get(
        "/api/v1/auth/configuracion/admin"
    ).json()

    assert datos["openrouter"]["configurado"] is False
    assert datos["openrouter"]["modelo"] == ""


def test_diagnotico_lista_todos_los_limites_del_etl(monkeypatch):
    from app.services import etl_service

    datos = _cliente(monkeypatch, Settings()).get(
        "/api/v1/auth/configuracion/admin"
    ).json()

    assert datos["ingesta"]["max_filas_archivo"] == etl_service.MAX_FILAS_ARCHIVO
    assert (
        datos["ingesta"]["max_lineas_texto_archivo"]
        == etl_service.MAX_LINEAS_TEXTO_ARCHIVO
    )
    assert datos["ingesta"]["max_paginas_pdf"] == etl_service.MAX_PAGINAS_PDF
    assert datos["ingesta"]["max_paginas_docx"] == etl_service.MAX_PAGINAS_DOCX
