"""Esquemas de productos e ingesta de catalogos."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.usuario_schema import PATRON_CORREO, PATRON_NOMBRE

EstadoArchivo = Literal["pendiente", "procesando", "ok", "parcial", "error", "rechazado"]

PATRON_PROVEEDOR = re.compile(
    r"[^\W_][^\W_\u0300-\u036f .,'’&()/#+-]*",
    re.UNICODE,
)
PATRON_TELEFONO = re.compile(
    r"(?=(?:[^0-9]*[0-9]){7,15}[^0-9]*$)\+?[0-9][0-9\s().-]*"
)


class MetadatosCatalogo(BaseModel):
    """Proveedor, contacto y condiciones generales de una cotizacion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proveedor: str = Field(min_length=2, max_length=255)
    vendedor: str = Field(min_length=2, max_length=255)
    telefono_vendedor: str | None = Field(default=None, max_length=40)
    correo_vendedor: str | None = Field(default=None, max_length=255)
    moneda: Literal["USD", "VES"] = "USD"
    nota_proveedor: str | None = Field(default=None, max_length=4000)

    @field_validator("proveedor")
    @classmethod
    def validar_proveedor(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("El proveedor es obligatorio")
        if not PATRON_PROVEEDOR.fullmatch(valor):
            raise ValueError(
                "El proveedor admite letras, numeros y signos comunes de razon social"
            )
        return valor

    @field_validator("vendedor")
    @classmethod
    def validar_vendedor(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("El vendedor es obligatorio")
        if not PATRON_NOMBRE.fullmatch(valor):
            raise ValueError(
                "El vendedor admite letras, espacios, apostrofes, puntos y guiones"
            )
        return valor

    @field_validator("telefono_vendedor", "correo_vendedor", "nota_proveedor")
    @classmethod
    def vacio_a_nulo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None

    @field_validator("telefono_vendedor")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor and not PATRON_TELEFONO.fullmatch(valor):
            raise ValueError(
                "El telefono debe tener entre 7 y 15 digitos; puede usar +, "
                "espacios, parentesis, puntos o guiones"
            )
        return valor

    @field_validator("correo_vendedor")
    @classmethod
    def validar_correo(cls, valor: str | None) -> str | None:
        if valor and not PATRON_CORREO.fullmatch(valor):
            raise ValueError("El correo del vendedor no tiene un formato valido")
        return valor


class ArchivoIngesta(BaseModel):
    """Resultado persistido o rechazado de un archivo del lote."""

    model_config = ConfigDict(from_attributes=True)

    id_archivo: int | None = None
    nombre: str
    tipo: str
    fecha_de_subida: datetime | None = None
    tamano_bytes: int = Field(ge=0)
    estado: EstadoArchivo
    filas_ok: int = Field(default=0, ge=0)
    filas_error: int = Field(default=0, ge=0)
    detalle: str | None = None
    proveedor: str | None = None
    vendedor: str | None = None
    moneda: str | None = None


class EstadoVectorizacion(BaseModel):
    """Cobertura del indice de busqueda del catalogo.

    Un producto sin vector no aparece en la recuperacion semantica: para el
    asistente no existe. El panel muestra este dato para que la vectorizacion
    no se olvide despues de cada carga; `en_curso` avisa si un lote
    automatico esta indexando en este momento, para que el panel vuelva a
    consultar hasta que el contador baje a cero.
    """

    total: int = Field(ge=0, description="Productos del catalogo")
    pendientes: int = Field(
        ge=0, description="Productos aun sin descripcion_vectorial"
    )
    en_curso: bool = Field(
        default=False, description="Hay un lote automatico indexando ahora"
    )


class RespuestaEliminacionArchivo(BaseModel):
    """Resultado de retirar un catalogo y sus datos asociados."""

    id_archivo: int
    nombre: str
    productos_eliminados: int = Field(ge=0)
    archivo_original_eliminado: bool


class SolicitudEliminacionCatalogos(BaseModel):
    """IDs de catalogos seleccionados para eliminacion en lote."""

    model_config = ConfigDict(extra="forbid")

    ids_archivos: list[Annotated[int, Field(ge=1)]] = Field(
        min_length=2,
        max_length=100,
    )

    @field_validator("ids_archivos")
    @classmethod
    def validar_ids_unicos(cls, ids: list[int]) -> list[int]:
        if len(set(ids)) != len(ids):
            raise ValueError("Los catalogos seleccionados no pueden repetirse")
        return ids


class RespuestaEliminacionCatalogos(BaseModel):
    """Resultados del borrado y IDs que ya no existian."""

    eliminados: list[RespuestaEliminacionArchivo]
    ids_no_encontrados: list[int]


class RespuestaIngesta(BaseModel):
    """Resumen de un lote de archivos de catalogo."""

    resultados: list[ArchivoIngesta]
    total_archivos: int = Field(ge=0)
    archivos_ok: int = Field(ge=0)
    archivos_parciales: int = Field(ge=0)
    archivos_error: int = Field(ge=0)
    archivos_rechazados: int = Field(ge=0)