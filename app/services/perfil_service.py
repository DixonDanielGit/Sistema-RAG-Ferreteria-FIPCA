"""Validacion y normalizacion de las imagenes de perfil."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGEN_PERFIL_BYTES = 2 * 1024 * 1024
MAX_PIXELES_IMAGEN_PERFIL = 16_000_000
FORMATOS_IMAGEN_PERFIL = {"JPEG", "PNG", "WEBP"}


class ImagenPerfilInvalida(ValueError):
    """La carga no contiene una imagen de perfil admitida."""


def normalizar_imagen_perfil(contenido: bytes) -> bytes:
    """Valida una imagen y la reserializa como WebP sin metadatos de origen."""
    if not contenido:
        raise ImagenPerfilInvalida("La imagen esta vacia")
    if len(contenido) > MAX_IMAGEN_PERFIL_BYTES:
        raise ImagenPerfilInvalida("La imagen supera el limite de 2 MB")

    datos = BytesIO(contenido)
    try:
        with Image.open(datos) as original:
            if original.format not in FORMATOS_IMAGEN_PERFIL:
                raise ImagenPerfilInvalida("Use una imagen JPEG, PNG o WebP")
            if getattr(original, "n_frames", 1) != 1:
                raise ImagenPerfilInvalida("No se admiten imagenes animadas")
            ancho, alto = original.size
            if ancho <= 0 or alto <= 0 or ancho * alto > MAX_PIXELES_IMAGEN_PERFIL:
                raise ImagenPerfilInvalida("La imagen tiene dimensiones no admitidas")
            original.verify()

        datos.seek(0)
        with Image.open(datos) as original:
            original.load()
            orientada = ImageOps.exif_transpose(original)
            modo = "RGBA" if "A" in orientada.getbands() else "RGB"
            imagen = orientada.convert(modo)
            salida = BytesIO()
            imagen.save(salida, format="WEBP", quality=85, method=5)
    except ImagenPerfilInvalida:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImagenPerfilInvalida("El archivo no contiene una imagen valida") from exc

    normalizada = salida.getvalue()
    if not normalizada or len(normalizada) > MAX_IMAGEN_PERFIL_BYTES:
        raise ImagenPerfilInvalida("La imagen procesada supera el limite de 2 MB")
    return normalizada
