"""Pruebas de integracion de la recuperacion de contrasena (Adenda 1).

Recorren el flujo completo contra la base clonada: solicitud, token, cambio de
contrasena, reutilizacion, caducidad y limite de intentos.
"""

from __future__ import annotations

import pytest

from app.services import email_service
from app.services import recuperacion_service


@pytest.fixture(autouse=True)
def limitador_limpio():
    recuperacion_service.limitador.reiniciar()
    yield
    recuperacion_service.limitador.reiniciar()


@pytest.fixture
def envios(monkeypatch):
    """Sustituye el envio de correo y expone los tokens generados."""
    capturados: list[dict] = []

    def falso(*, destinatario, nombre, token, minutos, settings=None):
        capturados.append(
            {"destinatario": destinatario, "nombre": nombre, "token": token, "minutos": minutos}
        )
        return email_service.ResultadoEnvio(enviado=True, modo="consola")

    monkeypatch.setattr(email_service, "enviar_enlace_recuperacion", falso)
    return capturados


def _solicitar(cliente, correo):
    cliente.cookies.clear()
    return cliente.post("/api/v1/auth/recuperar", json={"correo": correo})


class TestSolicitud:
    def test_un_correo_registrado_recibe_el_enlace(self, cliente, crear_cuenta, envios):
        cuenta = crear_cuenta(correo="ana@ferreteria.test")

        respuesta = _solicitar(cliente, cuenta["correo"])

        assert respuesta.status_code == 200
        assert "si el correo" in respuesta.json()["mensaje"].lower()
        assert len(envios) == 1
        assert envios[0]["destinatario"] == cuenta["correo"]
        assert len(envios[0]["token"]) >= 40

    def test_un_correo_inexistente_responde_exactamente_igual(
        self, cliente, crear_cuenta, envios
    ):
        cuenta = crear_cuenta(correo="ana@ferreteria.test")

        con_cuenta = _solicitar(cliente, cuenta["correo"])
        sin_cuenta = _solicitar(cliente, "nadie@ferreteria.test")

        assert con_cuenta.status_code == sin_cuenta.status_code == 200
        assert con_cuenta.json() == sin_cuenta.json()
        assert len(envios) == 1

    def test_una_cuenta_inactiva_no_recibe_enlace(self, cliente, crear_cuenta, envios):
        cuenta = crear_cuenta(correo="inactiva@ferreteria.test", activo=False)

        respuesta = _solicitar(cliente, cuenta["correo"])

        assert respuesta.status_code == 200
        assert envios == []

    def test_el_correo_invalido_se_rechaza(self, cliente):
        respuesta = cliente.post("/api/v1/auth/recuperar", json={"correo": "sin-arroba"})

        assert respuesta.status_code == 422
        datos = respuesta.json()
        assert datos["ok"] is False
        assert datos["errores"][0]["campo"] == "correo"
        assert "@dominio.com" in datos["errores"][0]["mensaje"]

    def test_el_limite_de_intentos_corta_la_rafaga(self, cliente, crear_cuenta, envios):
        cuenta = crear_cuenta(correo="ana@ferreteria.test")

        estados = [_solicitar(cliente, cuenta["correo"]).status_code for _ in range(6)]

        assert estados[:5] == [200] * 5
        assert estados[5] == 429

    def test_la_solicitud_queda_en_la_bitacora(
        self, cliente, crear_cuenta, envios, conexion_limpieza
    ):
        cuenta = crear_cuenta(correo="ana@ferreteria.test")
        _solicitar(cliente, cuenta["correo"])

        with conexion_limpieza.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bitacora WHERE accion LIKE 'solicitud de recuperacion%'"
            )
            assert cur.fetchone()[0] >= 1


class TestRestablecimiento:
    def _token(self, cliente, crear_cuenta, envios, correo="ana@ferreteria.test") -> tuple[dict, str]:
        cuenta = crear_cuenta(correo=correo)
        _solicitar(cliente, correo)
        return cuenta, envios[-1]["token"]

    def test_cambia_la_contrasena_y_permite_entrar(
        self, cliente, crear_cuenta, envios
    ):
        cuenta, token = self._token(cliente, crear_cuenta, envios)

        respuesta = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": token, "password": "ClaveNueva2026"},
        )

        assert respuesta.status_code == 200
        assert "actualizada" in respuesta.json()["mensaje"].lower()

        entrada = cliente.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": "ClaveNueva2026"},
        )
        assert entrada.status_code == 200

    def test_la_contrasena_anterior_deja_de_servir(self, cliente, crear_cuenta, envios):
        cuenta, token = self._token(cliente, crear_cuenta, envios)
        cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": token, "password": "ClaveNueva2026"},
        )

        respuesta = cliente.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )

        assert respuesta.status_code == 401

    def test_el_token_no_se_puede_reutilizar(self, cliente, crear_cuenta, envios):
        _, token = self._token(cliente, crear_cuenta, envios)

        primera = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": token, "password": "ClaveNueva2026"},
        )
        segunda = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": token, "password": "OtraClave2026"},
        )

        assert primera.status_code == 200
        assert segunda.status_code == 400

    def test_un_token_inventado_se_rechaza(self, cliente):
        respuesta = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": "a" * 43, "password": "ClaveNueva2026"},
        )
        assert respuesta.status_code == 400

    def test_un_token_vencido_se_rechaza(self, cliente, crear_cuenta, envios, conexion_limpieza):
        _, token = self._token(cliente, crear_cuenta, envios)

        with conexion_limpieza.cursor() as cur:
            # Se mueven ambas marcas: la restriccion chk_tokens_vigencia impide
            # dejar expira_en antes de creado_en (y eso es correcto).
            cur.execute(
                """
                UPDATE tokens_recuperacion
                   SET creado_en = NOW() - INTERVAL '2 hours',
                       expira_en = NOW() - INTERVAL '1 hour'
                """
            )

        respuesta = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": token, "password": "ClaveNueva2026"},
        )
        assert respuesta.status_code == 400

    def test_un_enlace_nuevo_anula_el_anterior(self, cliente, crear_cuenta, envios):
        cuenta = crear_cuenta(correo="ana@ferreteria.test")
        _solicitar(cliente, cuenta["correo"])
        primero = envios[-1]["token"]

        _solicitar(cliente, cuenta["correo"])
        segundo = envios[-1]["token"]

        anulado = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": primero, "password": "ClaveNueva2026"},
        )
        valido = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": segundo, "password": "ClaveNueva2026"},
        )

        assert anulado.status_code == 400
        assert valido.status_code == 200

    def test_la_contrasena_debil_se_rechaza_sin_gastar_el_token(
        self, cliente, crear_cuenta, envios
    ):
        _, token = self._token(cliente, crear_cuenta, envios)

        debil = cliente.post(
            "/api/v1/auth/restablecer", json={"token": token, "password": "12345678"}
        )
        valida = cliente.post(
            "/api/v1/auth/restablecer",
            json={"token": token, "password": "ClaveNueva2026"},
        )

        assert debil.status_code == 422
        assert valida.status_code == 200

    def test_el_token_se_guarda_hasheado(
        self, cliente, crear_cuenta, envios, conexion_limpieza
    ):
        _, token = self._token(cliente, crear_cuenta, envios)

        with conexion_limpieza.cursor() as cur:
            cur.execute("SELECT token_hash FROM tokens_recuperacion ORDER BY id DESC LIMIT 1")
            guardado = cur.fetchone()[0]

        assert guardado != token
        assert len(guardado) == 64
        assert token not in guardado
