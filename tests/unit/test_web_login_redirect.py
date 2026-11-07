"""Pruebas unitarias de la redireccion de la pagina de inicio de sesion."""

from starlette.requests import Request

from app.api.v1 import web


def test_sesion_activa_en_login_redirige_al_buscador(monkeypatch):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/login",
        "raw_path": b"/login",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    }
    monkeypatch.setattr(web, "_sesion", lambda _request: {"id": 1})

    respuesta = web.login(Request(scope))

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/search"
