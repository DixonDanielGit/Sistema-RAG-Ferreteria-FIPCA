"""Validaciones de los datos de contacto de una cotizacion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.inventario_schema import MetadatosCatalogo


def metadatos(**cambios):
    datos = {
        "proveedor": "Ferre-Inversiones Pérez C.A.",
        "vendedor": "María José Pérez",
    }
    datos.update(cambios)
    return MetadatosCatalogo(**datos)


@pytest.mark.parametrize(
    "proveedor",
    ["Ferre-Inversiones Pérez C.A.", "3M", "Casa & Hogar (Centro)", "Acme/Sur #2"],
)
def test_acepta_nombres_comerciales_comunes(proveedor):
    assert metadatos(proveedor=proveedor).proveedor == proveedor


@pytest.mark.parametrize("proveedor", ["", "  ", "_Proveedor", "Proveedor!?"])
def test_rechaza_nombre_de_proveedor_con_formato_invalido(proveedor):
    with pytest.raises(ValidationError):
        metadatos(proveedor=proveedor)


@pytest.mark.parametrize("vendedor", ["María José Pérez", "Jean-Luc O'Neil", "J. Pérez"])
def test_acepta_nombre_de_vendedor_segun_regla_del_sistema(vendedor):
    assert metadatos(vendedor=vendedor).vendedor == vendedor


@pytest.mark.parametrize("vendedor", ["Vendedor2", "123", "Ana_"])
def test_rechaza_nombre_de_vendedor_con_formato_invalido(vendedor):
    with pytest.raises(ValidationError):
        metadatos(vendedor=vendedor)


@pytest.mark.parametrize(
    "telefono",
    ["0412-1234567", "+58 (412) 123.4567", "2125551234"],
)
def test_acepta_telefonos_con_formato_comun(telefono):
    assert metadatos(telefono_vendedor=telefono).telefono_vendedor == telefono


@pytest.mark.parametrize("telefono", ["12345", "+58 ABC 1234567", "1234567890123456"])
def test_rechaza_telefono_con_formato_invalido(telefono):
    with pytest.raises(ValidationError):
        metadatos(telefono_vendedor=telefono)


def test_acepta_correo_con_patron_del_sistema():
    assert (
        metadatos(correo_vendedor="Compras+Catalogos@ferreteria.test")
        .correo_vendedor
        == "compras+catalogos@ferreteria.test"
    )


@pytest.mark.parametrize("correo", ["ventas@-empresa.com", "nombre..apellido@empresa.com"])
def test_rechaza_correo_que_no_cumple_patron_del_sistema(correo):
    with pytest.raises(ValidationError):
        metadatos(correo_vendedor=correo)
