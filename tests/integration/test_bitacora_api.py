"""Pruebas del visor de bitacora (RF-05.2)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import bitacora

pytestmark = pytest.mark.usefixtures("usuarios_limpios")

RUTA = "/api/v1/bitacora"
LOGIN = "/api/v1/auth/login"


def _cabecera(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_web(cliente, cuenta: dict) -> None:
    respuesta = cliente.post(
        LOGIN,
        json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
    )
    assert respuesta.status_code == 200, respuesta.text


def _registrar_eventos(cuenta: dict) -> None:
    bitacora.registrar(
        id_usuario=cuenta["id"],
        accion="carga de catalogo de prueba",
        ip="10.0.0.1",
        modulo="inventario",
    )
    bitacora.registrar(
        id_usuario=cuenta["id"],
        accion="consulta de permisos del sistema",
        ip="10.0.0.2",
        modulo="auth",
    )


class TestPermisos:
    def test_admin_puede_consultar(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        respuesta = cliente.get(RUTA, headers=_cabecera(token_de(cuenta)))

        assert respuesta.status_code == 200
        eventos = respuesta.json()
        assert isinstance(eventos, list)
        assert any("login exitoso" in evento["accion"] for evento in eventos)
        assert {"id_bitacora", "fecha", "hora", "accion"} <= set(eventos[0])

    def test_rol_sin_capacidad_recibe_403(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="ventas")
        respuesta = cliente.get(RUTA, headers=_cabecera(token_de(cuenta)))

        assert respuesta.status_code == 403
        eventos = bitacora.listar(limite=10)
        assert any(
            evento["modulo"] == "bitacora" and "403" in evento["accion"]
            for evento in eventos
        )

    def test_sin_sesion_recibe_401(self, cliente):
        respuesta = cliente.get(RUTA)

        assert respuesta.status_code == 401

    def test_capacidad_disponible_para_asignar_en_roles(
        self, cliente, crear_cuenta, token_de
    ):
        cuenta = crear_cuenta(rol="admin")
        respuesta = cliente.get(
            "/api/v1/auth/roles/permisos", headers=_cabecera(token_de(cuenta))
        )

        assert respuesta.status_code == 200
        assert "bitacora:consultar" in [
            permiso["clave"] for permiso in respuesta.json()
        ]


class TestFiltros:
    def test_filtra_por_modulo(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)
        _registrar_eventos(cuenta)

        respuesta = cliente.get(
            RUTA, params={"modulo": "inventario"}, headers=_cabecera(token)
        )

        assert respuesta.status_code == 200
        assert [evento["accion"] for evento in respuesta.json()] == [
            "carga de catalogo de prueba"
        ]

    def test_filtra_por_usuario(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)
        _registrar_eventos(cuenta)

        respuesta = cliente.get(
            RUTA, params={"usuario": "super"}, headers=_cabecera(token)
        )

        assert respuesta.status_code == 200
        assert len(respuesta.json()) == 3

    def test_filtra_por_ip(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)
        _registrar_eventos(cuenta)

        respuesta = cliente.get(
            RUTA, params={"ip": "10.0.0.2"}, headers=_cabecera(token)
        )

        assert respuesta.status_code == 200
        assert [evento["accion"] for evento in respuesta.json()] == [
            "consulta de permisos del sistema"
        ]

    def test_filtra_por_fechas(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)
        _registrar_eventos(cuenta)
        hoy = date.today()

        respuesta = cliente.get(
            RUTA,
            params={
                "desde": (hoy - timedelta(days=1)).isoformat(),
                "hasta": (hoy + timedelta(days=1)).isoformat(),
            },
            headers=_cabecera(token),
        )
        assert respuesta.status_code == 200
        assert respuesta.json()

        vacia = cliente.get(
            RUTA, params={"hasta": "2000-01-01"}, headers=_cabecera(token)
        )
        assert vacia.status_code == 200
        assert vacia.json() == []

    def test_orden_descendente(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)
        _registrar_eventos(cuenta)

        respuesta = cliente.get(
            RUTA, params={"limite": 10}, headers=_cabecera(token)
        )

        assert respuesta.status_code == 200
        eventos = respuesta.json()
        assert eventos[0]["accion"] == "consulta de permisos del sistema"
        assert eventos[1]["accion"] == "carga de catalogo de prueba"

    def test_lista_modulos(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)
        _registrar_eventos(cuenta)

        respuesta = cliente.get(RUTA + "/modulos", headers=_cabecera(token))

        assert respuesta.status_code == 200
        modulos = respuesta.json()
        assert "inventario" in modulos
        assert "auth" in modulos


class TestValidacion:
    def test_fechas_invertidas(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)

        respuesta = cliente.get(
            RUTA,
            params={"desde": "2026-11-05", "hasta": "2026-11-01"},
            headers=_cabecera(token),
        )

        assert respuesta.status_code == 400

    @pytest.mark.parametrize("limite", [0, -1, 501])
    def test_limite_fuera_de_rango(
        self, cliente, crear_cuenta, token_de, limite
    ):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)

        respuesta = cliente.get(
            RUTA, params={"limite": limite}, headers=_cabecera(token)
        )

        assert respuesta.status_code == 422

    def test_no_permite_escritura(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(rol="admin")
        token = token_de(cuenta)

        assert (
            cliente.post(RUTA, headers=_cabecera(token), json={}).status_code
            == 405
        )
        assert cliente.delete(RUTA, headers=_cabecera(token)).status_code == 405


class TestVistaWeb:
    def test_admin_ve_la_pagina(self, cliente, crear_cuenta):
        cuenta = crear_cuenta(rol="admin")
        _login_web(cliente, cuenta)

        respuesta = cliente.get("/bitacora")

        assert respuesta.status_code == 200
        assert "Bitácora" in respuesta.text

    def test_rol_sin_capacidad_redirige_al_panel(self, cliente, crear_cuenta):
        cuenta = crear_cuenta(rol="ventas")
        _login_web(cliente, cuenta)

        respuesta = cliente.get("/bitacora", follow_redirects=False)

        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/dashboard"

    def test_sin_sesion_redirige_al_login(self, cliente):
        respuesta = cliente.get("/bitacora", follow_redirects=False)

        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/login"
