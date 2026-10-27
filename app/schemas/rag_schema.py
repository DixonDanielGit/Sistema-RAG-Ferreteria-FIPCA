"""Esquemas del chat RAG (RF-03 / RF-06).

El contrato se define aqui desde la Semana 2.5, aunque el motor RAG llegue en
la Semana 5: asi la interfaz web se construye y se prueba contra la forma
definitiva y el reemplazo del servicio no obliga a tocar el frontend.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

LONGITUD_MAXIMA_PREGUNTA = 2000
LONGITUD_MINIMA_PREGUNTA = 1


class PreguntaChat(BaseModel):
    """Consulta del usuario al asistente."""

    model_config = ConfigDict(extra="forbid")

    pregunta: str = Field(
        min_length=LONGITUD_MINIMA_PREGUNTA,
        max_length=LONGITUD_MAXIMA_PREGUNTA,
        description="Pregunta en lenguaje natural sobre el inventario",
    )

    @field_validator("pregunta")
    @classmethod
    def _limpiar(cls, valor: str) -> str:
        limpio = " ".join(valor.split())
        if not limpio:
            raise ValueError("La pregunta no puede estar vacia")
        if any(c in limpio for c in "\0\r"):
            raise ValueError("La pregunta contiene caracteres no permitidos")
        return limpio


class FuenteProducto(BaseModel):
    """Producto del catalogo que respalda la respuesta (anti-alucinacion)."""

    model_config = ConfigDict(extra="ignore")

    codigo: str | None = None
    nombre: str
    marca: str | None = None
    precio: float
    stock: int
    categoria: str | None = None


class RespuestaChat(BaseModel):
    """Respuesta del asistente con las fuentes consultadas."""

    respuesta: str
    fuentes: list[FuenteProducto] = Field(default_factory=list)
    modelo: str = Field(description="Motor que genero la respuesta")
    aviso: str | None = Field(
        default=None,
        description="Nota para el usuario (por ejemplo, si el motor es provisional)",
    )
