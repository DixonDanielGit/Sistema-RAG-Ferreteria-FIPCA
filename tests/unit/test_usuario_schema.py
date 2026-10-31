"""Pruebas unitarias de validacion de entrada para cuentas y autenticacion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.usuario_schema import (
    LoginRequest,
    PerfilActualizar,
    RecuperarPasswordRequest,
    RestablecerPasswordRequest,
    RolActualizar,
    UsuarioAdminActualizar,
    UsuarioRegistro,
)


def datos_registro(**cambios) -> dict[str, str]:
    datos = {
        "cedula": "V-12345678",
        "nombre": "Ana Maria",
        "apellido": "Perez",
        "usuario": "ana.perez",
        "correo": "ana.perez@ferreteria.test",
        "password": "ClaveSegura123",
    }
    datos.update(cambios)
    return datos


def datos_perfil(**cambios) -> dict[str, str]:
    datos = {
        "cedula": "V-12345678",
        "nombre": "Ana Maria",
        "apellido": "Perez",
        "usuario": "ana.perez",
        "correo": "ana.perez@ferreteria.test",
    }
    datos.update(cambios)
    return datos


class TestEsquemaRegistro:
    def test_login_normaliza_y_valida_usuario_o_correo(self):
        usuario = LoginRequest(identificador=" Ana.Perez ", password="x")
        correo = LoginRequest(
            identificador=" Ana.Perez@Ferreteria.Test ",
            password="x",
        )

        assert usuario.identificador == "ana.perez"
        assert correo.identificador == "ana.perez@ferreteria.test"

    @pytest.mark.parametrize(
        "identificador",
        ["uno", " ana ", "ana@-ferreteria.test", "ana..perez@ferreteria.test"],
    )
    def test_login_rechaza_identificadores_invalidos(self, identificador):
        with pytest.raises(ValidationError):
            LoginRequest(identificador=identificador, password="ClaveSegura123")

    def test_normaliza_identificadores_y_rol(self):
        datos = UsuarioRegistro(
            **datos_registro(
                cedula=" v-12345678 ",
                usuario=" Ana.Perez ",
                correo=" Ana.Perez+Ventas@Sub.Ferreteria.Test ",
                rol=" ADMIN ",
            )
        )

        assert datos.cedula == "V-12345678"
        assert datos.usuario == "ana.perez"
        assert datos.correo == "ana.perez+ventas@sub.ferreteria.test"
        assert datos.rol == "admin"

    @pytest.mark.parametrize(
        "cambio",
        [
            {"cedula": "V-١٢٣٤٥٦٧٨"},
            {"cedula": "V-1234567890"},
            {"nombre": "Ana2"},
            {"usuario": ".ana"},
            {"usuario": "ana."},
            {"usuario": "ana perez"},
            {"correo": "ana..perez@ferreteria.test"},
            {"correo": "ana@-ferreteria.test"},
            {"correo": "ana@ferreteria-.test"},
            {"correo": "ana@ferreteria.c"},
            {"rol": "supervisor"},
            {"password": "Clave1"},
            {"password": "12345678"},
        ],
    )
    def test_rechaza_datos_que_no_cumplen_las_reglas(self, cambio):
        with pytest.raises(ValidationError):
            UsuarioRegistro(**datos_registro(**cambio))

    def test_rechaza_campos_no_declarados(self):
        with pytest.raises(ValidationError):
            UsuarioRegistro(**datos_registro(es_admin=True))

    def test_login_no_aplica_politica_de_alta_a_contrasenas_legacy(self):
        datos = LoginRequest(identificador="ana.perez", password="x")

        assert datos.password == "x"


class TestEsquemasDePerfilYRoles:
    def test_perfil_normaliza_y_comparte_validadores_del_registro(self):
        datos = PerfilActualizar(
            **datos_perfil(correo=" ANA.PEREZ+PERFIL@Ferreteria.Test ")
        )

        assert datos.correo == "ana.perez+perfil@ferreteria.test"

    @pytest.mark.parametrize(
        "esquema, datos",
        [
            (PerfilActualizar, datos_perfil(correo="ana@-ferreteria.test")),
            (
                UsuarioAdminActualizar,
                {**datos_perfil(), "rol": "supervisor"},
            ),
            (RolActualizar, {"rol": "supervisor"}),
        ],
    )
    def test_rechaza_reglas_invalidas_en_cada_operacion(self, esquema, datos):
        with pytest.raises(ValidationError):
            esquema(**datos)

    def test_normaliza_rol_de_actualizacion(self):
        assert RolActualizar(rol=" ADMIN ").rol == "admin"

    def test_perfil_no_permite_editar_campos_administrativos(self):
        with pytest.raises(ValidationError):
            PerfilActualizar(**datos_perfil(rol="admin"))


class TestEsquemasDeRecuperacion:
    def test_normaliza_correo_de_recuperacion(self):
        datos = RecuperarPasswordRequest(correo=" Ana.Perez@Ferreteria.Test ")

        assert datos.correo == "ana.perez@ferreteria.test"

    @pytest.mark.parametrize(
        "correo",
        [
            "ana..perez@ferreteria.test",
            "ana@-ferreteria.test",
            "ana@ferreteria-.test",
            "ana@ferreteria.c",
        ],
    )
    def test_rechaza_correo_malformado(self, correo):
        with pytest.raises(ValidationError):
            RecuperarPasswordRequest(correo=correo)

    def test_restablecer_password_aplica_longitud_y_fortaleza(self):
        with pytest.raises(ValidationError):
            RestablecerPasswordRequest(token="a" * 32, password="Clave1")

        datos = RestablecerPasswordRequest(
            token="a" * 32,
            password="ClaveSegura123",
        )
        assert datos.password == "ClaveSegura123"
