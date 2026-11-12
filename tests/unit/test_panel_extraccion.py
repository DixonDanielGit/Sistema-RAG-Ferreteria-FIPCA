"""El boton de prueba de extraccion solo se pinta en desarrollo.

La prueba muestra el JSON leido de los archivos del proveedor en pantalla,
por eso no debe existir en una instalacion de produccion. Se verifica el
filtrado por entorno en la plantilla, sin depender del JavaScript.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import web
from app.config import get_settings

USUARIO = {
    "id": 5,
    "nombre": "Ana",
    "apellido": "Perez",
    "rol": "ventas",
    "permisos": [],
}


def _cliente(monkeypatch, *, produccion: bool) -> TestClient:
    config = replace(get_settings(), entorno="produccion" if produccion else "desarrollo")
    monkeypatch.setattr(web, "get_settings", lambda: config)
    monkeypatch.setattr(web, "_sesion", lambda _request: dict(USUARIO))

    aplicacion = FastAPI()
    aplicacion.include_router(web.router)
    return TestClient(aplicacion)


def test_boton_de_extraccion_aparece_en_desarrollo(monkeypatch):
    respuesta = _cliente(monkeypatch, produccion=False).get("/search")

    assert respuesta.status_code == 200
    html = respuesta.text
    assert 'id="boton-extraccion"' in html
    assert 'id="salida-extraccion"' in html
    assert "Probar extraccion" in html


def test_boton_de_extraccion_no_aparece_en_produccion(monkeypatch):
    respuesta = _cliente(monkeypatch, produccion=True).get("/search")

    assert respuesta.status_code == 200
    html = respuesta.text
    assert 'id="boton-extraccion"' not in html
    assert 'id="salida-extraccion"' not in html


def test_boton_de_extraccion_no_depende_del_permiso_de_ingesta(monkeypatch):
    """El endpoint solo exige sesion, asi que el boton tampoco pide permiso."""
    assert USUARIO["permisos"] == []
    respuesta = _cliente(monkeypatch, produccion=False).get("/search")
    html = respuesta.text

    assert 'id="boton-extraccion"' in html
    assert 'id="archivos-extraccion"' in html
    # La cuenta no puede ingestar: la zona de carga no debe existir.
    assert 'id="zona-archivos"' not in html


def test_la_prueba_tiene_su_propio_selector_aun_con_permiso_de_ingesta(monkeypatch):
    """La zona de carga sube a /ingesta al soltar el archivo, asi que la
    prueba de extraccion necesita su propio selector para no guardar nada."""
    ingestor = {**USUARIO, "permisos": ["catalogos:ingestar"]}
    monkeypatch.setattr(web, "_sesion", lambda _request: dict(ingestor))
    config = replace(get_settings(), entorno="desarrollo")
    monkeypatch.setattr(web, "get_settings", lambda: config)

    aplicacion = FastAPI()
    aplicacion.include_router(web.router)
    html = TestClient(aplicacion).get("/search").text

    assert 'id="zona-archivos"' in html
    assert 'id="boton-extraccion"' in html
    assert 'id="archivos-extraccion"' in html
