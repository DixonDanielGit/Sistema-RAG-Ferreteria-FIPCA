"""Pruebas del middleware de auditoria (RF-05.1).

Verifican que cada accion sensible deje un registro en la bitacora con el
usuario, el modulo y la IP de origen.
"""

from __future__ import annotations

import psycopg2
import pytest

from app.models import bitacora

pytestmark = pytest.mark.usefixtures("usuarios_limpios")

LOGIN = "/api/v1/auth/login"
REGISTRO = "/api/v1/auth/register"
ME = "/api/v1/auth/me"


def ultimo_evento() -> dict:
    eventos = bitacora.listar(limite=1)
    assert eventos, "No se registro ningun evento en la bitacora"
    return eventos[0]


class TestLoginAuditado:
    def test_login_exitoso_queda_registrado(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": cuenta["password"]}
        )

        evento = ultimo_evento()
        assert "login exitoso" in evento["accion"]
        assert cuenta["usuario"] in evento["accion"]
        assert evento["id_usuario"] == cuenta["id"]
        assert evento["modulo"] == "auth"
        assert evento["ip"]

    def test_login_fallido_por_usuario_inexistente_no_tiene_usuario(
        self, cliente, crear_cuenta
    ):
        crear_cuenta()

        cliente.post(LOGIN, json={"identificador": "fantasma", "password": "ClaveMala123"})

        evento = ultimo_evento()
        assert "inexistente" in evento["accion"]
        assert evento["id_usuario"] is None

    def test_login_fallido_por_contrasena_registra_el_usuario(
        self, cliente, crear_cuenta
    ):
        cuenta = crear_cuenta()

        cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": "ClaveMala123"}
        )

        evento = ultimo_evento()
        assert "contrasena incorrecta" in evento["accion"]
        assert evento["id_usuario"] == cuenta["id"]

    def test_cuenta_inactiva_queda_registrada(self, cliente, crear_cuenta):
        cuenta = crear_cuenta(usuario="retirado", activo=False)

        cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": cuenta["password"]}
        )

        assert "inactiva" in ultimo_evento()["accion"]

    def test_la_contrasena_nunca_se_escribe_en_la_bitacora(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": "ClaveMala123"}
        )

        assert "ClaveMala123" not in ultimo_evento()["accion"]


class TestErroresAuditados:
    def test_una_peticion_sin_token_queda_registrada(self, cliente, crear_cuenta):
        crear_cuenta()

        cliente.get(ME)

        evento = ultimo_evento()
        assert "401" in evento["accion"]
        assert evento["modulo"] == "auth"

    def test_un_payload_invalido_queda_registrado(self, cliente, crear_cuenta):
        crear_cuenta()

        cliente.post(LOGIN, json={"identificador": "supervisor"})

        evento = ultimo_evento()
        assert "422" in evento["accion"]

    def test_el_endpoint_de_salud_no_ensucia_la_bitacora(self, cliente, crear_cuenta):
        crear_cuenta()
        antes = len(bitacora.listar(limite=500))

        cliente.get("/salud")

        assert len(bitacora.listar(limite=500)) == antes


class TestAltasAuditadas:
    def test_el_registro_de_usuario_queda_registrado(self, cliente):
        respuesta = cliente.post(
            REGISTRO,
            json={
                "cedula": "V-12345678",
                "nombre": "Ana",
                "apellido": "Perez",
                "usuario": "supervisor",
                "correo": "supervisor@ferreteria.test",
                "password": "ClaveSegura123",
                "rol": "admin",
            },
        )

        assert respuesta.status_code == 201
        evento = ultimo_evento()
        assert "alta de usuario" in evento["accion"]
        assert "supervisor" in evento["accion"]

    def test_el_cierre_de_sesion_queda_registrado(
        self, cliente, crear_cuenta, token_de
    ):
        cuenta = crear_cuenta()

        cliente.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token_de(cuenta)}"},
        )

        evento = ultimo_evento()
        assert "cierre de sesion" in evento["accion"]
        assert evento["id_usuario"] == cuenta["id"]


class TestInmutabilidadDesdeLaApi:
    def test_la_api_puede_escribir_y_leer_pero_no_alterar(self, cliente, crear_cuenta):
        from app.config import get_settings

        crear_cuenta()
        cliente.post(LOGIN, json={"identificador": "fantasma", "password": "ClaveMala123"})
        assert bitacora.listar(limite=5), "La API deberia poder leer la bitacora"

        conexion = psycopg2.connect(get_settings().database_url_usuarios)
        conexion.autocommit = True
        try:
            with pytest.raises(psycopg2.Error):
                with conexion.cursor() as cur:
                    cur.execute("UPDATE bitacora SET accion = 'alterado'")
        finally:
            conexion.close()
