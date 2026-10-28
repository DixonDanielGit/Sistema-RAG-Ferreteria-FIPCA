"""Validacion y normalizacion de imagenes de perfil."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.services.perfil_service import (
    MAX_IMAGEN_PERFIL_BYTES,
    ImagenPerfilInvalida,
    normalizar_imagen_perfil,
)


def imagen_bytes(formato: str = "PNG", tamano: tuple[int, int] = (32, 24)) -> bytes:
    salida = BytesIO()
    Image.new("RGB", tamano, color=(35, 90, 180)).save(salida, format=formato)
    return salida.getvalue()


def test_normaliza_formatos_admitidos_a_webp():
    for formato in ("JPEG", "PNG", "WEBP"):
        normalizada = normalizar_imagen_perfil(imagen_bytes(formato))
        with Image.open(BytesIO(normalizada)) as imagen:
            assert imagen.format == "WEBP"
            assert imagen.size == (32, 24)


@pytest.mark.parametrize(
    "contenido",
    [b"", b"<svg></svg>", b"no es una imagen"],
)
def test_rechaza_contenido_vacio_o_no_admitido(contenido):
    with pytest.raises(ImagenPerfilInvalida):
        normalizar_imagen_perfil(contenido)


def test_rechaza_imagen_por_encima_del_limite():
    with pytest.raises(ImagenPerfilInvalida, match="2 MB"):
        normalizar_imagen_perfil(b"x" * (MAX_IMAGEN_PERFIL_BYTES + 1))


def test_rechaza_dimensiones_excesivas():
    with pytest.raises(ImagenPerfilInvalida, match="dimensiones"):
        normalizar_imagen_perfil(imagen_bytes(tamano=(5000, 5000)))
