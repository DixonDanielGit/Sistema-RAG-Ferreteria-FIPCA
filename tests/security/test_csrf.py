"""Pruebas de seguridad de la sesion web (Adenda 1).

La cookie de sesion viaja sola en cada peticion del navegador, asi que los
metodos que cambian estado deben exigir la cabecera CSRF. Estos controles
demuestran que un sitio externo no puede actuar en nombre del usuario.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def navegador(cliente):
    cliente.cookies.clear()
    yield cliente
    cliente.cookies.clear()


@pytest.fixture
def sesion(navegador, crear_cuenta):
    cuenta = crear_cuenta()
    respuesta = navegador.post(
        "/api/v1/auth/login",
        json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
    )
    assert respuesta.status_code == 200, respuesta.text
    return {"cuenta": cuenta, "csrf": navegador.cookies.get("csrf_token")}


class TestCsrf:
    def test_un_post_con_cookie_sin_csrf_se_bloquea(self, navegador, sesion):
        respuesta = navegador.post("/api/v1/auth/logout", json={})
        assert respuesta.status_code == 403

    def test_un_post_con_csrf_incorrecto_se_bloquea(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/auth/logout",
            json={},
            headers={"X-CSRF-Token": "x" * 43},
        )
        assert respuesta.status_code == 403

    def test_un_post_con_csrf_valido_se_permite(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/auth/logout",
            json={},
            headers={"X-CSRF-Token": sesion["csrf"]},
        )
        assert respuesta.status_code == 200

    def test_el_chat_tambien_exige_csrf(self, navegador, sesion):
        respuesta = navegador.post("/api/v1/rag/chat", json={"pregunta": "hola"})
        assert respuesta.status_code == 403

    def test_un_origen_externo_se_rechaza_aunque_traiga_csrf(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/auth/logout",
            json={},
            headers={
                "X-CSRF-Token": sesion["csrf"],
                "Origin": "https://sitio-malicioso.example",
            },
        )
        assert respuesta.status_code == 403

    def test_el_origen_propio_se_acepta(self, navegador, sesion):
        from app.config import get_settings

        origen = get_settings().url_base
        respuesta = navegador.post(
            "/api/v1/auth/logout",
            json={},
            headers={"X-CSRF-Token": sesion["csrf"], "Origin": origen},
        )
        assert respuesta.status_code == 200

    def test_el_token_por_cabecera_no_necesita_csrf(self, navegador, crear_cuenta):
        cuenta = crear_cuenta()
        entrada = navegador.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )
        token = entrada.json()["access_token"]
        navegador.cookies.clear()

        respuesta = navegador.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert respuesta.status_code == 200


class TestCookies:
    def test_la_cookie_csrf_no_es_httponly(self, navegador):
        respuesta = navegador.get("/login")
        galletas = " ".join(respuesta.headers.get_list("set-cookie")).lower()
        assert "csrf_token=" in galletas
        assert "httponly" not in galletas

    def test_la_cookie_de_sesion_no_aparece_en_el_html(self, navegador, sesion):
        html = navegador.get("/dashboard").text
        assert sesion["csrf"] in html  # el CSRF si debe estar
        assert navegador.cookies.get("access_token") not in html
