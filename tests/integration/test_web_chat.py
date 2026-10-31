"""Pruebas de integracion de la vista del chat (Adenda 1).

La vista existe antes que el motor RAG: estas pruebas fijan el contrato para
que la Semana 5 solo sustituya el servicio, sin tocar plantillas ni JavaScript.
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


class TestVistaDelChat:
    def test_sin_sesion_redirige_al_login(self, navegador):
        respuesta = navegador.get("/chat", follow_redirects=False)
        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/login"

    def test_con_sesion_muestra_la_conversacion(self, navegador, sesion):
        respuesta = navegador.get("/chat")

        assert respuesta.status_code == 200
        assert 'id="hilo"' in respuesta.text
        assert 'id="loader-vista"' in respuesta.text
        assert 'id="form-chat"' in respuesta.text
        assert 'id="pregunta"' in respuesta.text
        assert "Motor provisional" in respuesta.text

    def test_incluye_sugerencias_de_ejemplo(self, navegador, sesion):
        html = navegador.get("/chat").text
        assert html.count("data-pregunta=") >= 3

    def test_el_limite_de_caracteres_esta_en_el_html(self, navegador, sesion):
        assert 'maxlength="2000"' in navegador.get("/chat").text

    def test_carga_el_script_del_chat(self, navegador, sesion):
        assert "/static/js/chat.js" in navegador.get("/chat").text

    def test_chat_prepara_controles_de_paneles_para_pc(self, navegador, sesion):
        html = navegador.get("/chat").text

        assert 'id="alternar-fuentes-pc"' in html
        assert 'aria-controls="panel-fuentes"' in html
        assert 'id="alternar-sesiones-pc"' in html
        assert 'aria-controls="panel-sesiones"' in html
        assert 'id="panel-sesiones"' in html
        assert "Ejemplos visuales" in html
        assert "la gestión de sesiones" in html

    def test_chat_muestra_control_responsivo_para_sesiones(self, navegador, sesion):
        html = navegador.get("/chat").text

        assert 'id="abrir-sesiones"' in html
        assert 'aria-controls="panel-sesiones"' in html
        assert 'id="cerrar-sesiones"' in html
        assert 'id="velo-sesiones"' in html
        assert 'id="alternar-sesiones-pc"' in html
        assert "/static/js/fuentes.js" in html

    def test_la_navegacion_marca_el_modulo_activo(self, navegador, sesion):
        assert 'aria-current="page"' in navegador.get("/chat").text


@pytest.fixture
def sesion_ventas(navegador, crear_cuenta):
    cuenta = crear_cuenta(usuario="vendedor", rol="ventas")
    respuesta = navegador.post(
        "/api/v1/auth/login",
        json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
    )
    assert respuesta.status_code == 200, respuesta.text
    return cuenta


class TestPanelDeFuentes:
    """El panel conecta el flujo de ingesta de la Semana 3.

    El administrador ve los controles de carga y el rol de ventas puede
    consultar el historial sin recibir controles de escritura.
    """

    def test_incluye_el_panel_de_fuentes(self, navegador, sesion):
        html = navegador.get("/chat").text

        assert 'id="panel-fuentes"' in html
        assert "Agregue sus archivos aquí" in html
        assert 'id="archivos"' in html
        assert 'accept=".pdf,.xlsx,.docx,.txt"' in html
        assert "PDF, XLSX, DOCX o TXT" in html

    def test_la_carga_es_automatica_sin_boton_de_procesar(self, navegador, sesion):
        """La subida arranca sola al elegir archivos: no existe el boton
        "Procesar catalogo" y hay linea de estado con la cola de carga."""
        html = navegador.get("/chat").text

        assert "Procesar catálogo" not in html
        assert 'id="procesar-archivos"' not in html
        assert 'id="estado-fuentes"' in html
        assert 'id="texto-estado-fuentes"' in html

    def test_fuentes_tiene_buscador_de_catalogos(self, navegador, sesion):
        """La seccion de documentos incluye un campo de busqueda con su
        aviso de "sin coincidencias" para cuando el filtro no encuentre nada."""
        html = navegador.get("/chat").text

        assert 'id="busqueda-fuentes"' in html
        assert 'id="buscar-fuentes"' in html
        assert 'type="search"' in html
        assert "Buscar catálogo…" in html
        assert 'id="fuentes-sin-coincidencias"' in html
        assert "Ningún archivo coincide con la búsqueda." in html

    def test_carga_el_script_del_panel(self, navegador, sesion):
        assert "/static/js/fuentes.js" in navegador.get("/chat").text

    def test_admin_puede_seleccionar_varios_catalogos(self, navegador, sesion):
        html = navegador.get("/chat").text

        assert 'id="seleccionar-visibles"' in html
        assert 'id="eliminar-seleccionados"' in html
        assert "Marcar visibles" in html

    def test_el_boton_del_telefono_controla_el_panel(self, navegador, sesion):
        html = navegador.get("/chat").text

        assert 'aria-controls="panel-fuentes"' in html
        assert 'aria-expanded="false"' in html

    def test_el_panel_explica_la_validacion_y_el_historial(self, navegador, sesion):
        html = navegador.get("/chat").text
        assert (
            "Los catálogos se suben y procesan automáticamente al elegirlos" in html
        )
        assert "Mientras termina la carga no se pueden agregar más archivos" in html
        assert "PDF, XLSX, DOCX o TXT" in html

    def test_ventas_no_ve_los_controles_de_carga(self, navegador, sesion_ventas):
        html = navegador.get("/chat").text

        assert 'id="panel-fuentes"' in html
        assert 'id="archivos"' not in html
        assert 'id="seleccionar-visibles"' not in html
        assert 'id="eliminar-seleccionados"' not in html
        assert "Agregar archivo" not in html
        assert "Un administrador todavía no ha cargado el catálogo." in html

    def test_ventas_tambien_buscador_en_fuentes(self, navegador, sesion_ventas):
        """El buscador es de consulta: el rol de ventas tambien lo ve."""
        html = navegador.get("/chat").text

        assert 'id="buscar-fuentes"' in html
        assert 'id="fuentes-sin-coincidencias"' in html


class TestEndpointProvisional:
    def test_sin_token_responde_401(self, navegador):
        respuesta = navegador.post("/api/v1/rag/chat", json={"pregunta": "hola"})
        assert respuesta.status_code == 401

    def test_respeta_el_contrato_final(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/rag/chat",
            json={"pregunta": "cuantos martillos hay"},
            headers={"X-CSRF-Token": sesion["csrf"]},
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert set(cuerpo) == {"respuesta", "fuentes", "modelo", "aviso"}
        assert isinstance(cuerpo["respuesta"], str) and cuerpo["respuesta"]
        assert cuerpo["fuentes"] == []
        assert cuerpo["modelo"].startswith("provisional")

    def test_la_pregunta_vacia_se_rechaza(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/rag/chat",
            json={"pregunta": "   "},
            headers={"X-CSRF-Token": sesion["csrf"]},
        )
        assert respuesta.status_code == 422

    def test_la_pregunta_demasiado_larga_se_rechaza(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/rag/chat",
            json={"pregunta": "a" * 2001},
            headers={"X-CSRF-Token": sesion["csrf"]},
        )
        assert respuesta.status_code == 422

    def test_un_campo_extra_se_rechaza(self, navegador, sesion):
        respuesta = navegador.post(
            "/api/v1/rag/chat",
            json={"pregunta": "hola", "rol": "admin"},
            headers={"X-CSRF-Token": sesion["csrf"]},
        )
        assert respuesta.status_code == 422

    def test_la_consulta_queda_auditada(self, navegador, sesion, conexion_limpieza):
        navegador.post(
            "/api/v1/rag/chat",
            json={"pregunta": "cuantos martillos hay"},
            headers={"X-CSRF-Token": sesion["csrf"]},
        )

        with conexion_limpieza.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bitacora WHERE accion LIKE 'consulta al asistente%'")
            assert cur.fetchone()[0] >= 1

    def test_el_estado_informa_que_el_motor_es_provisional(self, navegador, sesion):
        respuesta = navegador.get("/api/v1/rag/estado")
        assert respuesta.status_code == 200
        assert respuesta.json()["disponible"] is False
