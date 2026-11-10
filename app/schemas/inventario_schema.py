"""Esquemas de productos e ingesta de catalogos."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.usuario_schema import PATRON_CORREO, PATRON_NOMBRE

EstadoArchivo = Literal["pendiente", "procesando", "ok", "parcial", "error", "rechazado"]

# Limites de consulta del Buscador Comercial (RF-03.1 / RNF-01.2).
LONGITUD_MINIMA_BUSQUEDA = 1
LONGITUD_MAXIMA_BUSQUEDA = 200
LIMITE_DEFECTO_BUSQUEDA = 50
LIMITE_MAXIMO_BUSQUEDA = 100

PATRON_PROVEEDOR = re.compile(
    r"[^\W_](?:[^\W_]|[\u0300-\u036f]|[ .,'’&()/#+_$-])*",
    re.UNICODE,
)
PATRON_TELEFONO = re.compile(
    r"(?=(?:[^0-9]*[0-9]){7,15}[^0-9]*$)\+?[0-9][0-9\s().-]*"
)


class MetadatosCatalogo(BaseModel):
    """Proveedor, contacto y condiciones generales de una cotizacion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proveedor: str | None = Field(default=None, min_length=2, max_length=255)
    vendedor: str | None = Field(default=None, max_length=255)
    telefono_vendedor: str | None = Field(default=None, max_length=40)
    correo_vendedor: str | None = Field(default=None, max_length=255)
    moneda: Literal["USD", "VES"] = "USD"
    nota_proveedor: str | None = Field(default=None, max_length=4000)

    @field_validator("proveedor")
    @classmethod
    def validar_proveedor(cls, valor: str | None) -> str | None:
        if valor and not PATRON_PROVEEDOR.fullmatch(valor):
            raise ValueError(
                "El proveedor admite letras, numeros y signos comunes de razon social"
            )
        return valor

    @field_validator("vendedor")
    @classmethod
    def validar_vendedor(cls, valor: str | None) -> str | None:
        if valor and not PATRON_NOMBRE.fullmatch(valor):
            raise ValueError(
                "El vendedor admite letras, espacios, apostrofes, puntos y guiones"
            )
        return valor

    @field_validator(
        "proveedor",
        "vendedor",
        "telefono_vendedor",
        "correo_vendedor",
        "nota_proveedor",
    )
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
        return valor.lower() if valor else None


class ArchivoIngesta(BaseModel):
    """Resultado persistido o rechazado de un archivo del lote."""

    model_config = ConfigDict(from_attributes=True)

    id_archivo: int | None = None
    nombre: str
    tipo: str
    fecha_de_subida: datetime | None = None
    tamano_bytes: int | None = Field(default=None, ge=0)
    estado: EstadoArchivo
    filas_ok: int = Field(default=0, ge=0)
    filas_error: int = Field(default=0, ge=0)
    detalle: str | None = None
    proveedor: str | None = None
    vendedor: str | None = None
    moneda: str | None = None
    respuesta_ia: dict[str, Any] | None = None


class ProductoBusqueda(BaseModel):
    """Coincidencia del catalogo devuelta por el Buscador Comercial (RF-03)."""

    model_config = ConfigDict(extra="ignore")

    id: int
    codigo: str | None = None
    nombre: str
    marca: str | None = None
    categoria: str | None = None
    proveedor: str | None = None
    descripcion: str | None = None
    presentacion: str | None = None
    precio: float
    iva: float
    descuentos: float = 0.0
    stock: int = 0
    moneda: str = "USD"
    relevancia: float | None = Field(
        default=None, description="ts_rank de PostgreSQL; no es un puntaje de IA"
    )


class ResultadoBusqueda(BaseModel):
    """Respuesta de una consulta del Buscador Comercial.

    Solo devuelve productos reales de la base: si no hay coincidencias,
    `productos` queda vacio y `total` en cero; el buscador nunca inventa
    filas ni inventa una respuesta en lenguaje natural.
    """

    consulta: str
    total: int = Field(ge=0, description="Coincidencias encontradas")
    pagina: int = Field(ge=1)
    limite: int = Field(ge=1)
    productos: list[ProductoBusqueda] = Field(default_factory=list)


class ResultadoCatalogo(BaseModel):
    """Pagina del catalogo activo para la vista completa del buscador."""

    total: int = Field(ge=0, description="Productos activos del catalogo")
    pagina: int = Field(ge=1)
    limite: int = Field(ge=1)
    productos: list[ProductoBusqueda] = Field(default_factory=list)


class ProductoDetalle(BaseModel):
    """Ficha completa de un producto consultada desde el buscador."""

    id: int
    codigo: str | None = None
    codigo_interno: str | None = None
    nombre: str
    marca: str | None = None
    categoria: str | None = None
    descripcion: str | None = None
    unidad_medida: str | None = None
    presentacion: str | None = None
    precio: float
    moneda: str
    iva: float
    descuentos: float
    stock: int
    punto_reorden: int | None = None
    ubicacion: str | None = None
    actualizado_en: datetime | None = None


class ProveedorProductoDetalle(BaseModel):
    """Datos registrados del proveedor asociado al producto."""

    id: int
    nombre: str
    rif: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    correo: str | None = None
    vendedor: str | None = None
    telefono_vendedor: str | None = None
    correo_vendedor: str | None = None
    moneda: str | None = None


class CatalogoProductoDetalle(BaseModel):
    """Archivo de origen y datos de su carga."""

    id: int
    nombre: str
    tipo: str
    fecha_de_subida: datetime
    estado: EstadoArchivo
    filas_ok: int = Field(ge=0)
    filas_error: int = Field(ge=0)
    moneda: str
    nota_proveedor: str | None = None
    vendedor: str | None = None
    telefono_vendedor: str | None = None
    correo_vendedor: str | None = None


class OfertaProductoDetalle(BaseModel):
    """Cotizacion de un proveedor para el producto."""

    id: int
    proveedor: str
    codigo_proveedor: str
    precio: float
    moneda: str
    iva: float
    iva_incluido: bool | None = None
    descuento: float | None = None
    cantidad_disponible_proveedor: int | None = None
    politica_ventas: str | None = None
    plazo_entrega_dias: int | None = None
    cantidad_minima: int
    disponible: bool | None = None
    fecha_cotizacion: date
    catalogo: str | None = None


class DetalleProducto(BaseModel):
    """Detalle comercial y trazabilidad del catálogo de origen."""

    producto: ProductoDetalle
    proveedor: ProveedorProductoDetalle | None = None
    catalogo: CatalogoProductoDetalle | None = None
    ofertas: list[OfertaProductoDetalle] = Field(default_factory=list)


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