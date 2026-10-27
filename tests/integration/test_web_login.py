"""Pruebas de integracion de la interfaz web (Adenda 1).

Verifican el contrato que el navegador necesita: HTML con formularios, cookie
de sesion ``HttpOnly``, redirecciones cuando no hay sesion y escape de HTML en
las plantillas.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def navegador(cliente):
    """Cliente sin cookies heredadas de otras pruebas."""
    cliente.cookies.clear()
    yield cliente
    cliente.cookies.clear()


def _entrar(navegador, cuenta) -> None:
    respuesta = navegador.post(
        "/api/v1/auth/login",
        json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
    )
    assert respuesta.status_code == 200, respuesta.text


class TestPaginaDeLogin:
    def test_responde_html_con_el_formulario(self, navegador):
        respuesta = navegador.get("/login")

        assert respuesta.status_code == 200
        assert "text/html" in respuesta.headers["content-type"]
        assert 'id="form-login"' in respuesta.text
        assert 'name="identificador"' in respuesta.text
        assert 'name="password"' in respuesta.text

    def test_publica_la_cookie_csrf(self, navegador):
        respuesta = navegador.get("/login")
        csrf = respuesta.cookies.get("csrf_token")

        assert csrf is not None
        assert len(csrf) >= 40
        assert csrf in respuesta.text

    def test_carga_los_estilos_y_scripts_propios(self, navegador):
        respuesta = navegador.get("/login")
        assert "/static/css/estilos.css" in respuesta.text
        assert "/static/js/login.js" in respuesta.text

    def test_no_expone_ningun_token_de_sesion(self, navegador):
        respuesta = navegador.get("/login")
        assert "access_token" not in respuesta.text
        assert "Bearer" not in respuesta.text

    def test_el_tema_se_aplica_antes_de_pintar(self, navegador):
        respuesta = navegador.get("/login")
        # El script debe estar en el <head>, antes de la hoja de estilos.
        posicion_script = respuesta.text.find("fipca-tema")
        posicion_css = respuesta.text.find("estilos.css")
        assert -1 < posicion_script < posicion_css

    def test_ofrece_modo_claro_y_oscuro(self, navegador):
        respuesta = navegador.get("/login")
        assert "data-tema-toggle" in respuesta.text
        assert "fipca-tema__luna" in respuesta.text


class TestSesionWeb:
    def test_el_login_deja_una_cookie_httponly(self, navegador, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = navegador.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )

        assert respuesta.status_code == 200
        galletas = " ".join(respuesta.headers.get_list("set-cookie")).lower()
        assert "access_token=" in galletas
        assert "httponly" in galletas
        assert "samesite=lax" in galletas
        assert "path=/" in galletas
        assert navegador.cookies.get("access_token")

    def test_la_cookie_no_se_marca_secure_en_desarrollo(self, navegador, crear_cuenta):
        cuenta = crear_cuenta()
        respuesta = navegador.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )
        galletas = " ".join(respuesta.headers.get_list("set-cookie")).lower()
        assert "secure" not in galletas

    def test_el_panel_redirige_sin_sesion(self, navegador):
        respuesta = navegador.get("/dashboard", follow_redirects=False)

        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/login"

    def test_el_panel_muestra_el_nombre_con_sesion(self, navegador, crear_cuenta):
        cuenta = crear_cuenta(nombre="Ana")
        _entrar(navegador, cuenta)

        respuesta = navegador.get("/dashboard")

        assert respuesta.status_code == 200
        assert "Ana" in respuesta.text
        assert cuenta["correo"] in respuesta.text

    def test_con_sesion_el_login_lleva_al_panel(self, navegador, crear_cuenta):
        _entrar(navegador, crear_cuenta())
        respuesta = navegador.get("/login", follow_redirects=False)

        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/dashboard"

    def test_el_logout_borra_las_cookies(self, navegador, crear_cuenta):
        _entrar(navegador, crear_cuenta())
        csrf = navegador.cookies.get("csrf_token")

        respuesta = navegador.post(
            "/api/v1/auth/logout",
            json={},
            headers={"X-CSRF-Token": csrf},
        )

        assert respuesta.status_code == 200
        assert navegador.cookies.get("access_token") is None

    def test_la_raiz_lleva_al_login_en_un_navegador(self, navegador):
        respuesta = navegador.get("/", headers={"Accept": "text/html"}, follow_redirects=False)
        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/login"

    def test_la_raiz_sigue_siendo_json_para_la_api(self, navegador):
        respuesta = navegador.get("/")
        assert respuesta.status_code == 200
        assert respuesta.json()["sistema"]


class TestEscapeDeHtml:
    def test_el_nombre_de_la_cuenta_no_se_interpreta_como_html(self, navegador, crear_cuenta):
        cuenta = crear_cuenta(nombre="<script>alert(1)</script>")
        _entrar(navegador, cuenta)

        html = navegador.get("/dashboard").text

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_el_correo_tambien_se_escapa(self, navegador, crear_cuenta, conexion_limpieza):
        # El esquema de alta no permitiria este correo; se inserta directo en la
        # base para comprobar que la plantilla escapa aunque el dato sea hostil.
        cuenta = crear_cuenta()
        with conexion_limpieza.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET correo = %s WHERE id = %s",
                ('"><img src=x onerror=alert(1)>@x.test', cuenta["id"]),
            )

        _entrar(navegador, cuenta)
        html = navegador.get("/dashboard").text
        assert "<img src=x" not in html
