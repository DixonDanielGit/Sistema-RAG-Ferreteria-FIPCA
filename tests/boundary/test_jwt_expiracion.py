"""Pruebas de valores limite de la expiracion de los JWT (RF-01.3).

Se trabaja con marcas de tiempo explicitas para no depender del reloj real ni
de esperas: el limite se comprueba al segundo exacto.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.config import Settings, get_settings
from app.core.jwt import TokenInvalido, crear_token, decodificar_token


@pytest.fixture
def config() -> Settings:
    return Settings(
        jwt_secret="clave-de-prueba-con-mas-de-32-caracteres-1234",
        jwt_emisor="ferreteria-test",
        jwt_expiracion_minutos=30,
        database_url_rag="postgresql://x/y",
        database_url_usuarios="postgresql://x/z",
    )


def _ahora() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _fabricar(config: Settings, *, exp: int, nbf: int | None = None, iat: int | None = None) -> str:
    claims = {
        "sub": "1",
        "usuario": "supervisor",
        "rol": "admin",
        "tipo": "access",
        "iss": config.jwt_emisor,
        "iat": iat if iat is not None else _ahora(),
        "exp": exp,
    }
    if nbf is not None:
        claims["nbf"] = nbf
    return pyjwt.encode(claims, config.jwt_secret, algorithm="HS256")


class TestLimiteDeExpiracion:
    def test_un_segundo_antes_de_vencer_sigue_siendo_valido(self, config):
        token = _fabricar(config, exp=_ahora() + 1)

        assert decodificar_token(token, settings=config)["sub"] == "1"

    def test_en_el_instante_exacto_de_vencimiento_es_rechazado(self, config):
        # Limite cerrado: al segundo exacto de "exp" el token ya no sirve.
        # Es la interpretacion de PyJWT (exp <= ahora -> vencido), la mas
        # conservadora posible.
        token = _fabricar(config, exp=_ahora())

        with pytest.raises(TokenInvalido, match="expiro"):
            decodificar_token(token, settings=config)

    def test_un_segundo_despues_de_vencer_es_rechazado(self, config):
        token = _fabricar(config, exp=_ahora() - 1)

        with pytest.raises(TokenInvalido, match="expiro"):
            decodificar_token(token, settings=config)

    def test_la_tolerancia_de_reloj_acepta_un_vencimiento_reciente(self, config):
        token = _fabricar(config, exp=_ahora() - 5)

        with pytest.raises(TokenInvalido):
            decodificar_token(token, settings=config)

        assert decodificar_token(token, settings=config, leeway_segundos=30)["sub"] == "1"

    def test_la_tolerancia_de_reloj_tiene_su_propio_limite(self, config):
        token = _fabricar(config, exp=_ahora() - 31)

        with pytest.raises(TokenInvalido):
            decodificar_token(token, settings=config, leeway_segundos=30)

    def test_un_vencimiento_muy_lejano_es_valido(self, config):
        año_3000 = int(datetime(3000, 1, 1, tzinfo=timezone.utc).timestamp())
        token = _fabricar(config, exp=año_3000)

        assert decodificar_token(token, settings=config)["sub"] == "1"

    def test_una_expiracion_no_numerica_es_rechazada(self, config):
        token = pyjwt.encode(
            {
                "sub": "1",
                "tipo": "access",
                "iss": config.jwt_emisor,
                "iat": _ahora(),
                "exp": "manana",
            },
            config.jwt_secret,
            algorithm="HS256",
        )

        with pytest.raises(TokenInvalido):
            decodificar_token(token, settings=config)


class TestLimiteDeInicioDeValidez:
    def test_un_token_que_empieza_en_el_futuro_es_rechazado(self, config):
        token = _fabricar(config, exp=_ahora() + 600, nbf=_ahora() + 60)

        with pytest.raises(TokenInvalido, match="todavia no es valido"):
            decodificar_token(token, settings=config)

    def test_la_tolerancia_permite_un_desfase_pequeno(self, config):
        token = _fabricar(config, exp=_ahora() + 600, nbf=_ahora() + 10)

        assert (
            decodificar_token(token, settings=config, leeway_segundos=30)["sub"] == "1"
        )


class TestDuracionConfigurable:
    @pytest.mark.parametrize("minutos", [1, 15, 30, 60, 1440])
    def test_la_duracion_se_respeta_exactamente(self, config, minutos):
        generado = crear_token(1, "supervisor", "admin", minutos=minutos, settings=config)

        assert generado.claims["exp"] - generado.claims["iat"] == minutos * 60

    def test_una_duracion_de_un_minuto_ya_esta_vencida_pasados_dos(self, config):
        generado = crear_token(
            1,
            "supervisor",
            "admin",
            minutos=1,
            emitido_en=datetime.now(timezone.utc) - timedelta(minutes=2),
            settings=config,
        )

        with pytest.raises(TokenInvalido):
            decodificar_token(generado.token, settings=config)


class TestExpiracionEnLaApi:
    def test_un_token_vencido_no_accede_a_la_cuenta(
        self, cliente, crear_cuenta, token_de
    ):
        cuenta = crear_cuenta()
        generado = crear_token(
            cuenta["id"],
            cuenta["usuario"],
            cuenta["rol"],
            minutos=30,
            emitido_en=datetime.now(timezone.utc) - timedelta(hours=3),
            settings=get_settings(),
        )

        respuesta = cliente.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {generado.token}"}
        )

        assert respuesta.status_code == 401
        assert "expiro" in respuesta.json()["detail"].lower()

    def test_un_token_recien_emitido_accede(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()

        respuesta = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de(cuenta)}"},
        )

        assert respuesta.status_code == 200

    def test_un_token_sin_expiracion_es_rechazado_por_la_api(
        self, cliente, crear_cuenta
    ):
        cuenta = crear_cuenta()
        config = get_settings()
        sin_exp = pyjwt.encode(
            {
                "sub": str(cuenta["id"]),
                "usuario": cuenta["usuario"],
                "rol": cuenta["rol"],
                "tipo": "access",
                "iss": config.jwt_emisor,
                "iat": _ahora(),
            },
            config.jwt_secret,
            algorithm=config.jwt_algoritmo,
        )

        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {sin_exp}"})

        assert respuesta.status_code == 401
