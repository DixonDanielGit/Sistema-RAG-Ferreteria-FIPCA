"""Pruebas de caja blanca de la emision y validacion de JWT (RF-01.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.config import Settings
from app.core.jwt import (
    TIPO_TOKEN,
    TokenInvalido,
    crear_token,
    decodificar_token,
    segundos_para_expirar,
)

SECRETO = "clave-de-prueba-con-mas-de-32-caracteres-1234"
EMISOR = "ferreteria-test"


@pytest.fixture
def config() -> Settings:
    return Settings(
        jwt_secret=SECRETO,
        jwt_emisor=EMISOR,
        jwt_expiracion_minutos=30,
        jwt_algoritmo="HS256",
        database_url_rag="postgresql://x/y",
        database_url_usuarios="postgresql://x/z",
    )


class TestEmision:
    def test_contiene_los_claims_esperados(self, config):
        generado = crear_token(7, "supervisor", "admin", settings=config)
        claims = decodificar_token(generado.token, settings=config)

        assert claims["sub"] == "7"
        assert claims["id_usuario"] == 7
        assert claims["usuario"] == "supervisor"
        assert claims["rol"] == "admin"
        assert claims["tipo"] == TIPO_TOKEN
        assert claims["iss"] == EMISOR
        assert claims["jti"]
        assert claims["exp"] > claims["iat"]

    def test_la_expiracion_respeta_la_configuracion(self, config):
        generado = crear_token(7, "supervisor", "admin", settings=config)

        assert generado.claims["exp"] - generado.claims["iat"] == 30 * 60
        assert 29 * 60 <= generado.segundos_restantes <= 30 * 60

    def test_minutos_personalizados(self, config):
        generado = crear_token(7, "supervisor", "admin", minutos=5, settings=config)

        assert generado.claims["exp"] - generado.claims["iat"] == 5 * 60

    def test_cada_token_tiene_identificador_unico(self, config):
        primero = crear_token(7, "supervisor", "admin", settings=config)
        segundo = crear_token(7, "supervisor", "admin", settings=config)

        assert primero.claims["jti"] != segundo.claims["jti"]

    @pytest.mark.parametrize("minutos", [0, -1, -60])
    def test_rechaza_duraciones_no_positivas(self, config, minutos):
        with pytest.raises(ValueError, match="mayor que cero"):
            crear_token(7, "supervisor", "admin", minutos=minutos, settings=config)

    @pytest.mark.parametrize("id_usuario", [0, -5, "7", None])
    def test_rechaza_identificadores_invalidos(self, config, id_usuario):
        with pytest.raises(ValueError):
            crear_token(id_usuario, "supervisor", "admin", settings=config)

    @pytest.mark.parametrize("campo", ["", "   "])
    def test_rechaza_usuario_o_rol_vacios(self, config, campo):
        with pytest.raises(ValueError):
            crear_token(1, campo, "admin", settings=config)

        with pytest.raises(ValueError):
            crear_token(1, "supervisor", campo, settings=config)

    def test_sin_secreto_no_emite_tokens(self):
        config = Settings(
            jwt_secret="",
            jwt_emisor=EMISOR,
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )

        with pytest.raises(ValueError, match="JWT_SECRET"):
            crear_token(1, "supervisor", "admin", settings=config)


class TestValidacion:
    def test_rechaza_firma_manipulada(self, config):
        token = crear_token(7, "supervisor", "admin", settings=config).token
        cuerpo, firma = token.rsplit(".", 1)
        alterado = f"{cuerpo}.{'A' * len(firma)}"

        with pytest.raises(TokenInvalido):
            decodificar_token(alterado, settings=config)

    def test_rechaza_un_token_firmado_con_otra_clave(self, config):
        otra_config = Settings(
            jwt_secret="otra-clave-distinta-con-32-caracteres-000",
            jwt_emisor=EMISOR,
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )
        token = crear_token(7, "supervisor", "admin", settings=otra_config).token

        with pytest.raises(TokenInvalido):
            decodificar_token(token, settings=config)

    def test_rechaza_token_vencido(self, config):
        emitido = datetime.now(timezone.utc) - timedelta(hours=2)
        token = crear_token(
            7, "supervisor", "admin", minutos=30, emitido_en=emitido, settings=config
        ).token

        with pytest.raises(TokenInvalido, match="expiro"):
            decodificar_token(token, settings=config)

    def test_rechaza_el_algoritmo_none(self, config):
        sin_firma = pyjwt.encode(
            {
                "sub": "7",
                "tipo": TIPO_TOKEN,
                "iss": EMISOR,
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
            },
            key="",
            algorithm="none",
        )

        with pytest.raises(TokenInvalido):
            decodificar_token(sin_firma, settings=config)

    def test_rechaza_token_sin_expiracion(self, config):
        sin_exp = pyjwt.encode(
            {
                "sub": "7",
                "tipo": TIPO_TOKEN,
                "iss": EMISOR,
                "iat": int(datetime.now(timezone.utc).timestamp()),
            },
            SECRETO,
            algorithm="HS256",
        )

        with pytest.raises(TokenInvalido):
            decodificar_token(sin_exp, settings=config)

    def test_rechaza_emisor_distinto(self, config):
        ajeno = Settings(
            jwt_secret=SECRETO,
            jwt_emisor="otro-sistema",
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )
        token = crear_token(7, "supervisor", "admin", settings=ajeno).token

        with pytest.raises(TokenInvalido, match="emitido"):
            decodificar_token(token, settings=config)

    def test_rechaza_tokens_que_no_son_de_acceso(self, config):
        refresco = pyjwt.encode(
            {
                "sub": "7",
                "tipo": "refresh",
                "iss": EMISOR,
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
            },
            SECRETO,
            algorithm="HS256",
        )

        with pytest.raises(TokenInvalido, match="acceso"):
            decodificar_token(refresco, settings=config)

    @pytest.mark.parametrize("token", ["", "   ", "abc", "a.b.c", None, 12345])
    def test_rechaza_tokens_mal_formados(self, config, token):
        with pytest.raises(TokenInvalido):
            decodificar_token(token, settings=config)

    def test_rechaza_identificador_de_usuario_no_numerico(self, config):
        token = pyjwt.encode(
            {
                "sub": "admin",
                "tipo": TIPO_TOKEN,
                "iss": EMISOR,
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
            },
            SECRETO,
            algorithm="HS256",
        )

        with pytest.raises(TokenInvalido, match="identificador"):
            decodificar_token(token, settings=config)

    def test_rechaza_identificador_negativo(self, config):
        token = pyjwt.encode(
            {
                "sub": "-3",
                "tipo": TIPO_TOKEN,
                "iss": EMISOR,
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
            },
            SECRETO,
            algorithm="HS256",
        )

        with pytest.raises(TokenInvalido, match="identificador"):
            decodificar_token(token, settings=config)


class TestUtilidades:
    def test_segundos_para_expirar_es_positivo(self, config):
        claims = crear_token(7, "supervisor", "admin", settings=config).claims

        assert 0 < segundos_para_expirar(claims) <= 30 * 60

    def test_segundos_para_expirar_es_cero_si_ya_vencio(self):
        vencido = {"exp": int(datetime.now(timezone.utc).timestamp()) - 500}

        assert segundos_para_expirar(vencido) == 0


class TestConfiguracion:
    def test_rechaza_secreto_corto(self):
        config = Settings(
            jwt_secret="corto",
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )

        with pytest.raises(ValueError, match="32"):
            config.validar()

    def test_rechaza_secreto_vacio(self):
        config = Settings(
            jwt_secret="",
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )

        with pytest.raises(ValueError, match="JWT_SECRET"):
            config.validar()

    def test_rechaza_algoritmo_no_simetrico(self):
        config = Settings(
            jwt_secret=SECRETO,
            jwt_algoritmo="none",
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )

        with pytest.raises(ValueError, match="JWT_ALGORITHM"):
            config.validar()

    def test_rechaza_falta_de_cadenas_de_conexion(self):
        config = Settings(jwt_secret=SECRETO, database_url_rag="", database_url_usuarios="")

        with pytest.raises(ValueError, match="DATABASE_URL"):
            config.validar()

    def test_acepta_configuracion_completa(self):
        Settings(
            jwt_secret=SECRETO,
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        ).validar()

    def test_en_produccion_rechaza_el_secreto_de_ejemplo(self):
        config = Settings(
            jwt_secret="cambia_esta_clave_de_firma_pero_mas_larga",
            entorno="produccion",
            database_url_rag="postgresql://x/y",
            database_url_usuarios="postgresql://x/z",
        )

        with pytest.raises(ValueError, match="ejemplo"):
            config.validar()
