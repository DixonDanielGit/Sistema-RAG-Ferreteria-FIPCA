"""Pruebas de caja blanca del modulo de contrasenas (RNF-02.1).

No requieren base de datos: verifican el algoritmo de hashing de forma aislada.
"""

from __future__ import annotations

import base64
import time

import pytest

from app.core import security


class TestHashing:
    def test_el_hash_no_contiene_la_contrasena(self):
        hash_generado = security.hash_password("ClaveSegura123")

        assert "ClaveSegura123" not in hash_generado
        assert "clavesegura123" not in hash_generado.lower()

    def test_dos_hashes_de_la_misma_clave_son_distintos(self):
        primero = security.hash_password("ClaveSegura123")
        segundo = security.hash_password("ClaveSegura123")

        assert primero != segundo, "Falta la sal aleatoria: hashes identicos"

    def test_el_formato_guarda_los_parametros(self):
        partes = security.hash_password("ClaveSegura123").split("$")

        assert len(partes) == 6
        assert partes[0] == "scrypt"
        assert int(partes[1]) == security.N
        assert int(partes[2]) == security.R
        assert int(partes[3]) == security.P

    def test_la_sal_es_aleatoria_y_decodificable(self):
        sal_1 = base64.b64decode(security.hash_password("ClaveSegura123").split("$")[4])
        sal_2 = base64.b64decode(security.hash_password("ClaveSegura123").split("$")[4])

        assert len(sal_1) == security.SAL_LONGITUD
        assert sal_1 != sal_2

    def test_verifica_la_contrasena_correcta(self):
        hash_generado = security.hash_password("ClaveSegura123")

        assert security.verify_password("ClaveSegura123", hash_generado) is True

    def test_rechaza_la_contrasena_incorrecta(self):
        hash_generado = security.hash_password("ClaveSegura123")

        assert security.verify_password("ClaveSegura124", hash_generado) is False
        assert security.verify_password("clavesegura123", hash_generado) is False
        assert security.verify_password("", hash_generado) is False

    def test_rechaza_la_contrasena_con_espacio_extra(self):
        hash_generado = security.hash_password("ClaveSegura123")

        assert security.verify_password("ClaveSegura123 ", hash_generado) is False

    def test_costo_razonable_para_un_login(self):
        inicio = time.perf_counter()
        hash_generado = security.hash_password("ClaveSegura123")
        security.verify_password("ClaveSegura123", hash_generado)
        duracion = time.perf_counter() - inicio

        assert duracion < 1.5, f"El hashing tarda demasiado: {duracion:.2f}s"

    def test_admite_acentos_y_simbolos(self):
        clave = "contraseña-ñ-2026!#%"
        hash_generado = security.hash_password(clave)

        assert security.verify_password(clave, hash_generado) is True
        assert security.verify_password("contrasena-ñ-2026!#%", hash_generado) is False


class TestHashesInvalidos:
    @pytest.mark.parametrize(
        "hash_invalido",
        [
            "",
            "texto-plano",
            "scrypt$16384$8$1$solo-cinco-partes",
            "bcrypt$12$abcdefghijklmnopqrstuv",
            "scrypt$abc$8$1$c2Fs$aGFzaA==",
            "scrypt$16384$8$1$!!!$aGFzaA==",
            "scrypt$1$1$1$c2Fs$aGFzaA==",
            None,
            12345,
        ],
    )
    def test_hash_corrupto_devuelve_false(self, hash_invalido):
        assert security.verify_password("ClaveSegura123", hash_invalido) is False

    def test_parametros_absurdos_no_agotan_la_memoria(self):
        # n=2**30 exigiria terabytes de RAM: debe rechazarse, no colgar.
        hash_malicioso = "scrypt$1073741824$8$1$c2Fs$aGFzaA=="

        assert security.verify_password("ClaveSegura123", hash_malicioso) is False

    def test_contrasena_none_no_lanza_excepcion(self):
        hash_generado = security.hash_password("ClaveSegura123")

        assert security.verify_password(None, hash_generado) is False


class TestPoliticaDeContrasenas:
    @pytest.mark.parametrize(
        "password",
        [
            "",
            "Corta1",
            "12345678",
            "sinNumeros",
            "1234567890",
            " ClaveSegura123",
            "ClaveSegura123 ",
            "a" * (security.LONGITUD_MAXIMA + 1),
        ],
    )
    def test_rechaza_contrasenas_debiles(self, password):
        with pytest.raises(security.PasswordInvalida):
            security.hash_password(password)

    @pytest.mark.parametrize(
        "password",
        [
            "ClaveSegura123",
            "abcdefg1",
            "A1" * 4,
            "contraseña2026",
            "a" * (security.LONGITUD_MAXIMA - 1) + "1",
        ],
    )
    def test_acepta_contrasenas_validas(self, password):
        assert security.verify_password(password, security.hash_password(password))

    def test_mensaje_de_error_en_espanol(self):
        with pytest.raises(security.PasswordInvalida) as error:
            security.hash_password("corta1")

        assert "al menos" in str(error.value)


class TestRehash:
    def test_un_hash_actual_no_necesita_rehash(self):
        assert security.necesita_rehash(security.hash_password("ClaveSegura123")) is False

    def test_un_hash_con_parametros_antiguos_necesita_rehash(self):
        hash_antiguo = "scrypt$1024$8$1$c2Fs$aGFzaA=="

        assert security.necesita_rehash(hash_antiguo) is True

    def test_un_hash_corrupto_necesita_rehash(self):
        assert security.necesita_rehash("basura") is True


def test_gastar_tiempo_no_lanza_excepcion():
    # Se usa cuando el usuario no existe: debe consumir el mismo tiempo.
    security.gastar_tiempo_como_si_existiera("ClaveSegura123")
