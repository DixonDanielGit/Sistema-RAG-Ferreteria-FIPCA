"""Pruebas de caja negra del flujo de autenticacion (RF-01).

Se ejercita la API como lo haria el frontend: solo peticiones HTTP y
respuestas. No se inspecciona el codigo, sino el comportamiento observable.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("usuarios_limpios")

LOGIN = "/api/v1/auth/login"
REGISTRO = "/api/v1/auth/register"
ME = "/api/v1/auth/me"


def datos_registro(**cambios) -> dict:
    base = {
        "cedula": "V-12345678",
        "nombre": "Ana",
        "apellido": "Perez",
        "usuario": "supervisor",
        "correo": "supervisor@ferreteria.test",
        "password": "ClaveSegura123",
        "rol": "admin",
    }
    base.update(cambios)
    return base


class TestLogin:
    def test_login_exitoso_entrega_token(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": cuenta["password"]}
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["token_type"] == "bearer"
        assert cuerpo["access_token"].count(".") == 2
        assert cuerpo["expira_en"] > 0
        assert cuerpo["usuario"]["usuario"] == cuenta["usuario"]
        assert cuerpo["usuario"]["rol"] == "admin"

    def test_la_respuesta_no_expone_el_hash(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": cuenta["password"]}
        )

        texto = respuesta.text.lower()
        assert "password" not in texto
        assert "scrypt" not in texto

    def test_login_con_correo(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN, json={"identificador": cuenta["correo"], "password": cuenta["password"]}
        )

        assert respuesta.status_code == 200

    def test_login_ignora_mayusculas_en_el_identificador(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN,
            json={"identificador": cuenta["usuario"].upper(), "password": cuenta["password"]},
        )

        assert respuesta.status_code == 200

    def test_password_incorrecta_es_rechazada(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN,
            json={"identificador": cuenta["usuario"], "password": "ClaveIncorrecta999"},
        )

        assert respuesta.status_code == 401
        assert respuesta.headers["www-authenticate"] == "Bearer"

    def test_usuario_inexistente_da_el_mismo_mensaje(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        con_clave_mala = cliente.post(
            LOGIN,
            json={"identificador": cuenta["usuario"], "password": "ClaveIncorrecta999"},
        )
        sin_usuario = cliente.post(
            LOGIN,
            json={"identificador": "fantasma", "password": "ClaveIncorrecta999"},
        )

        assert sin_usuario.status_code == 401
        assert sin_usuario.json()["detail"] == con_clave_mala.json()["detail"]

    def test_cuenta_inactiva_es_rechazada(self, cliente, crear_cuenta):
        cuenta = crear_cuenta(usuario="retirado", activo=False)

        respuesta = cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": cuenta["password"]}
        )

        assert respuesta.status_code == 403
        assert "inactiva" in respuesta.json()["detail"].lower()

    @pytest.mark.parametrize("usuario", ["uno", "1"])
    def test_rechaza_usuario_existente_con_formato_invalido(
        self, cliente, crear_cuenta, usuario
    ):
        cuenta = crear_cuenta(usuario=usuario)

        respuesta = cliente.post(
            LOGIN,
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )

        assert respuesta.status_code == 422
        datos = respuesta.json()
        assert datos["ok"] is False
        assert "Usuario o correo" in datos["detail"]
        assert "entre 4 y 50 caracteres" in datos["detail"]
        assert datos["errores"][0]["campo"] == "identificador"
        assert datos["errores"][0]["etiqueta"] == "Usuario o correo"

    @pytest.mark.parametrize(
        "cuerpo",
        [
            {},
            {"identificador": "supervisor"},
            {"password": "ClaveSegura123"},
            {"identificador": "", "password": "ClaveSegura123"},
            {"identificador": "   ", "password": "ClaveSegura123"},
            {"identificador": "supervisor", "password": ""},
            {"identificador": "supervisor", "password": "x" * 200},
        ],
    )
    def test_peticiones_incompletas_devuelven_422(self, cliente, cuerpo):
        assert cliente.post(LOGIN, json=cuerpo).status_code == 422

    def test_campos_extra_son_rechazados(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN,
            json={
                "identificador": cuenta["usuario"],
                "password": cuenta["password"],
                "rol": "admin",
            },
        )

        assert respuesta.status_code == 422


class TestCuentaActual:
    def test_me_devuelve_los_datos_sin_password(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()

        respuesta = cliente.get(ME, headers={"Authorization": f"Bearer {token_de(cuenta)}"})

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["usuario"] == cuenta["usuario"]
        assert cuerpo["correo"] == cuenta["correo"]
        assert "password" not in cuerpo

    def test_me_sin_token_devuelve_401(self, cliente):
        respuesta = cliente.get(ME)

        assert respuesta.status_code == 401

    @pytest.mark.parametrize("token", ["basura", "a.b.c", "Bearer x", ""])
    def test_me_con_token_invalido_devuelve_401(self, cliente, token):
        respuesta = cliente.get(ME, headers={"Authorization": f"Bearer {token}"})

        assert respuesta.status_code == 401

    def test_me_de_una_cuenta_desactivada_devuelve_403(
        self, cliente, crear_cuenta, token_de
    ):
        from app.models import usuario as modelo

        cuenta = crear_cuenta()
        token = token_de(cuenta)
        modelo.cambiar_estado(cuenta["id"], False)

        respuesta = cliente.get(ME, headers={"Authorization": f"Bearer {token}"})

        assert respuesta.status_code == 403


class TestRoles:
    def test_admin_puede_listar_roles(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")

        respuesta = cliente.get(
            "/api/v1/auth/roles", headers={"Authorization": f"Bearer {token_de(cuenta)}"}
        )

        assert respuesta.status_code == 200
        assert {rol["nombre"] for rol in respuesta.json()} == {"admin", "ventas"}

    def test_ventas_no_puede_listar_roles(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(usuario="vendedor", rol="ventas")

        respuesta = cliente.get(
            "/api/v1/auth/roles", headers={"Authorization": f"Bearer {token_de(cuenta)}"}
        )

        assert respuesta.status_code == 403

    def test_logout_registra_y_responde(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_de(cuenta)}"}
        )

        assert respuesta.status_code == 200
        assert "cerrada" in respuesta.json()["mensaje"].lower()


class TestRegistro:
    def test_la_primera_cuenta_se_crea_sin_token(self, cliente):
        respuesta = cliente.post(REGISTRO, json=datos_registro())

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["usuario"] == "supervisor"
        assert cuerpo["rol"] == "admin"
        assert cuerpo["activo"] is True
        assert "password" not in cuerpo

    def test_la_primera_cuenta_debe_ser_administrador(self, cliente):
        respuesta = cliente.post(REGISTRO, json=datos_registro(rol="ventas"))

        assert respuesta.status_code == 400
        assert "administrador" in respuesta.json()["detail"].lower()

    def test_sin_token_y_con_usuarios_existentes_devuelve_401(
        self, cliente, crear_cuenta
    ):
        crear_cuenta()

        respuesta = cliente.post(
            REGISTRO, json=datos_registro(usuario="otro", correo="otro@ferreteria.test")
        )

        assert respuesta.status_code == 401

    def test_un_administrador_puede_crear_usuarios(self, cliente, crear_cuenta, token_de):
        admin = crear_cuenta(rol="admin")

        respuesta = cliente.post(
            REGISTRO,
            json=datos_registro(
                usuario="vendedor", correo="vendedor@ferreteria.test", rol="ventas"
            ),
            headers={"Authorization": f"Bearer {token_de(admin)}"},
        )

        assert respuesta.status_code == 201
        assert respuesta.json()["rol"] == "ventas"

    def test_ventas_no_puede_crear_usuarios(self, cliente, crear_cuenta, token_de):
        vendedor = crear_cuenta(usuario="vendedor", rol="ventas")

        respuesta = cliente.post(
            REGISTRO,
            json=datos_registro(usuario="intruso", correo="intruso@ferreteria.test"),
            headers={"Authorization": f"Bearer {token_de(vendedor)}"},
        )

        assert respuesta.status_code == 403

    @pytest.mark.parametrize(
        "cambio, campo",
        [
            ({"usuario": "supervisor"}, "usuario"),
            ({"correo": "supervisor@ferreteria.test"}, "correo"),
            ({"cedula": "V-12345678"}, "cedula"),
        ],
    )
    def test_no_permite_duplicados(self, cliente, crear_cuenta, token_de, cambio, campo):
        admin = crear_cuenta(usuario="jefe", rol="admin")
        cabecera = {"Authorization": f"Bearer {token_de(admin)}"}
        assert cliente.post(REGISTRO, json=datos_registro(), headers=cabecera).status_code == 201

        payload = datos_registro(usuario="otro", correo="otro@ferreteria.test", cedula="V-87654321")
        payload.update(cambio)

        respuesta = cliente.post(REGISTRO, json=payload, headers=cabecera)

        assert respuesta.status_code == 409
        assert campo in respuesta.json()["detail"]

    @pytest.mark.parametrize(
        "cambio",
        [
            {"password": "corta1"},
            {"password": "sinnumeros"},
            {"password": "1234567890"},
            {"usuario": "ab"},
            {"usuario": "con espacio"},
            {"usuario": "admin'; DROP TABLE usuarios; --"},
            {"correo": "sin-arroba"},
            {"correo": "dos@@arrobas.com"},
            {"correo": "ana@-ferreteria.test"},
            {"correo": "ana..perez@ferreteria.test"},
            {"cedula": "123"},
            {"nombre": "A1"},
            {"rol": "superusuario"},
        ],
    )
    def test_datos_invalidos_devuelven_422(self, cliente, crear_cuenta, token_de, cambio):
        admin = crear_cuenta(rol="admin")

        respuesta = cliente.post(
            REGISTRO,
            json=datos_registro(**cambio),
            headers={"Authorization": f"Bearer {token_de(admin)}"},
        )

        assert respuesta.status_code == 422


def test_endpoint_de_salud(cliente):
    respuesta = cliente.get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"


def test_la_raiz_describe_el_servicio(cliente):
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert respuesta.json()["empresa"] == "FERRE-INVERSIONES PEREZ C.A."
