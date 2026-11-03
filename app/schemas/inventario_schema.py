"""Esquemas de productos e ingesta de catalogos."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EstadoArchivo = Literal["pendiente", "procesando", "ok", "parcial", "error", "rechazado"]


class MetadatosCatalogo(BaseModel):
    """Proveedor, contacto y condiciones generales de una cotizacion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proveedor: str = Field(min_length=1, max_length=255)
    vendedor: str = Field(min_length=1, max_length=255)
    telefono_vendedor: str | None = Field(default=None, max_length=40)
    correo_vendedor: str | None = Field(default=None, max_length=255)
    moneda: Literal["USD", "VES"] = "USD"
    nota_proveedor: str | None = Field(default=None, max_length=4000)

    @field_validator("proveedor", "vendedor")
    @classmethod
    def validar_identidad(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("Este campo es obligatorio")
        return valor.strip()

    @field_validator("telefono_vendedor", "correo_vendedor", "nota_proveedor")
    @classmethod
    def vacio_a_nulo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None

    @field_validator("correo_vendedor")
    @classmethod
    def validar_correo(cls, valor: str | None) -> str | None:
        if valor and ("@" not in valor or valor.startswith("@") or valor.endswith("@")):
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