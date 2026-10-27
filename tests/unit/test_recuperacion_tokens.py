"""Pruebas unitarias de la recuperacion de contrasena (Adenda 1).

Cubren las piezas que no necesitan base de datos: generacion y hashing del
token, limite de intentos, armado del enlace, envio en modo consola y
validacion de los esquemas de entrada.
"""

from __future__ import annotations

import logging
import smtplib

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.security import (
    generar_token_csrf,
    generar_token_recuperacion,
    hash_token,
    tokens_coinciden,
)
from app.schemas.rag_schema import LONGITUD_MAXIMA_PREGUNTA, PreguntaChat
from app.schemas.usuario_schema import (
    RecuperarPasswordRequest,
    RestablecerPasswordRequest,
)
from app.services import email_service
from app.services.recuperacion_service import LimitadorIntentos, MENSAJE_SOLICITUD


class TestTokenDeRecuperacion:
    def test_el_hash_es_sha256_en_hexadecimal(self):
        huella = hash_token("un-token-cualquiera")
        assert len(huella) == 64
        assert set(huella) <= set("0123456789abcdef")

    def test_el_hash_es_determinista(self):
        assert hash_token("abc123") == hash_token("abc123")

    def test_tokens_distintos_dan_hashes_distintos(self):
        assert hash_token("abc123") != hash_token("abc124")

    def test_el_token_generado_es_impredecible(self):
        primero, _ = generar_token_recuperacion()
        segundo, _ = generar_token_recuperacion()
        assert primero != segundo
        assert len(primero) >= 40

    def test_el_token_generado_es_seguro_para_url(self):
        token, _ = generar_token_recuperacion()
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_el_hash_corresponde_al_token_entregado(self):
        token, huella = generar_token_recuperacion()
        assert huella == hash_token(token)

    def test_un_token_vacio_no_se_puede_hashear(self):
        with pytest.raises(ValueError):
            hash_token("")

    def test_comparacion_en_tiempo_constante(self):
        assert tokens_coinciden("abc", "abc") is True
        assert tokens_coinciden("abc", "abd") is False
        assert tokens_coinciden("abc", "abcd") is False

    def test_el_token_csrf_tambien_es_aleatorio(self):
        assert generar_token_csrf() != generar_token_csrf()


class TestLimitadorDeIntentos:
    def test_permite_hasta_el_maximo(self):
        limitador = LimitadorIntentos()
        for _ in range(3):
            assert limitador.permitir("ip", maximo=3, ventana_minutos=15) is True

    def test_bloquea_al_superar_el_maximo(self):
        limitador = LimitadorIntentos()
        for _ in range(3):
            limitador.permitir("ip", maximo=3, ventana_minutos=15)
        assert limitador.permitir("ip", maximo=3, ventana_minutos=15) is False

    def test_cada_clave_tiene_su_propio_contador(self):
        limitador = LimitadorIntentos()
        for _ in range(3):
            limitador.permitir("ip-1", maximo=3, ventana_minutos=15)
        assert limitador.permitir("ip-2", maximo=3, ventana_minutos=15) is True

    def test_reiniciar_limpia_el_estado(self):
        limitador = LimitadorIntentos()
        for _ in range(3):
            limitador.permitir("ip", maximo=3, ventana_minutos=15)
        limitador.reiniciar()
        assert limitador.permitir("ip", maximo=3, ventana_minutos=15) is True


class TestCorreo:
    def test_sin_smtp_el_enlace_va_al_log(self, caplog):
        config = Settings(smtp_host="", smtp_remitente="")
        with caplog.at_level(logging.WARNING, logger="ferreteria.correo"):
            resultado = email_service.enviar_enlace_recuperacion(
                destinatario="ana@ferreteria.test",
                nombre="Ana",
                token="token-de-prueba",
                minutos=30,
                settings=config,
            )

        assert resultado.enviado is True
        assert resultado.modo == "consola"
        assert "/restablecer?token=token-de-prueba" in caplog.text

    def test_el_enlace_usa_la_url_base_configurada(self):
        config = Settings(url_base="https://inventario.fipca.test")
        enlace = email_service.construir_enlace("abc123", config)
        assert enlace == "https://inventario.fipca.test/restablecer?token=abc123"

    def test_el_token_se_escapa_en_la_url(self):
        enlace = email_service.construir_enlace("a/b?c", Settings())
        assert "a%2Fb%3Fc" in enlace

    def test_un_fallo_de_smtp_no_lanza_excepcion(self, monkeypatch):
        config = Settings(smtp_host="smtp.invalido", smtp_remitente="no@reply.test")

        def explotar(*_args, **_kwargs):
            raise OSError("sin conexion")

        monkeypatch.setattr(smtplib, "SMTP", explotar)
        resultado = email_service.enviar_enlace_recuperacion(
            destinatario="ana@ferreteria.test",
            nombre="Ana",
            token="token",
            minutos=30,
            settings=config,
        )

        assert resultado.enviado is False
        assert resultado.modo == "error"

    def test_el_mensaje_publico_no_revela_si_el_correo_existe(self):
        assert "si el correo" in MENSAJE_SOLICITUD.lower()


class TestEsquemasDeRecuperacion:
    def test_correo_valido_se_normaliza(self):
        datos = RecuperarPasswordRequest(correo="  Ana.Perez@Ferreteria.COM ")
        assert datos.correo == "ana.perez@ferreteria.com"

    @pytest.mark.parametrize(
        "correo", ["sin-arroba", "a@b", "a b@c.com", "@ferreteria.com", ""]
    )
    def test_correo_invalido(self, correo):
        with pytest.raises(ValidationError):
            RecuperarPasswordRequest(correo=correo)

    def test_no_se_aceptan_campos_extra(self):
        with pytest.raises(ValidationError):
            RecuperarPasswordRequest(correo="ana@ferreteria.com", admin=True)

    def test_token_con_caracteres_raros_se_rechaza(self):
        with pytest.raises(ValidationError):
            RestablecerPasswordRequest(
                token="../../etc/passwd<?>", password="ClaveSegura123"
            )

    def test_token_demasiado_corto_se_rechaza(self):
        with pytest.raises(ValidationError):
            RestablecerPasswordRequest(token="corto", password="ClaveSegura123")

    def test_contrasena_debil_se_rechaza(self):
        with pytest.raises(ValidationError):
            RestablecerPasswordRequest(token="a" * 32, password="12345678")

    def test_contrasena_valida_se_acepta(self):
        datos = RestablecerPasswordRequest(token="a" * 32, password="ClaveSegura123")
        assert datos.password == "ClaveSegura123"


class TestEsquemaDeChat:
    def test_normaliza_espacios_en_la_pregunta(self):
        assert PreguntaChat(pregunta="  cuantos   martillos hay ").pregunta == (
            "cuantos martillos hay"
        )

    @pytest.mark.parametrize("pregunta", ["", "   ", "\n\t"])
    def test_pregunta_vacia_se_rechaza(self, pregunta):
        with pytest.raises(ValidationError):
            PreguntaChat(pregunta=pregunta)

    def test_pregunta_en_el_limite_se_acepta(self):
        datos = PreguntaChat(pregunta="a" * LONGITUD_MAXIMA_PREGUNTA)
        assert len(datos.pregunta) == LONGITUD_MAXIMA_PREGUNTA

    def test_pregunta_sobre_el_limite_se_rechaza(self):
        with pytest.raises(ValidationError):
            PreguntaChat(pregunta="a" * (LONGITUD_MAXIMA_PREGUNTA + 1))

    def test_el_esquema_no_admite_campos_extra(self):
        with pytest.raises(ValidationError):
            PreguntaChat(pregunta="hola", modelo="gpt")
