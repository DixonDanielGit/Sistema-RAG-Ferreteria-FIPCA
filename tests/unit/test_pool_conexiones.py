"""Pruebas unitarias del pool de conexiones (RNF-01).

Cubren el caso que aparece cuando PostgreSQL cierra conexiones inactivas: el
pool devuelve una conexion ya cerrada y la API no debe reutilizarla.
"""

from __future__ import annotations

import pytest

from app.db.session import BaseDeDatosNoDisponible, _PoolDiferido


class ConexionFalsa:
    def __init__(self, cerrada: bool = False) -> None:
        self.closed = 1 if cerrada else 0


class PoolFalso:
    def __init__(self, conexiones: list[ConexionFalsa]) -> None:
        self._cola = list(conexiones)
        self.devuelta: list[tuple[ConexionFalsa, bool]] = []

    def getconn(self) -> ConexionFalsa:
        return self._cola.pop(0)

    def putconn(self, conexion: ConexionFalsa, close: bool = False) -> None:
        self.devuelta.append((conexion, close))


class TestConexionesCerradas:
    def test_descarta_la_cerrada_y_entrega_la_siguiente(self):
        cerrada = ConexionFalsa(cerrada=True)
        viva = ConexionFalsa()
        pool = PoolFalso([cerrada, viva])
        diferido = _PoolDiferido("prueba", lambda _config: "")

        assert diferido._obtener_conexion(pool) is viva
        assert pool.devuelta == [(cerrada, True)]

    def test_si_todas_estan_cerradas_avisa_sin_reutilizarlas(self):
        primera = ConexionFalsa(cerrada=True)
        segunda = ConexionFalsa(cerrada=True)
        pool = PoolFalso([primera, segunda])
        diferido = _PoolDiferido("prueba", lambda _config: "")

        with pytest.raises(BaseDeDatosNoDisponible):
            diferido._obtener_conexion(pool)

        assert [conexion for conexion, _ in pool.devuelta] == [primera, segunda]
        assert all(cerrar for _, cerrar in pool.devuelta)
