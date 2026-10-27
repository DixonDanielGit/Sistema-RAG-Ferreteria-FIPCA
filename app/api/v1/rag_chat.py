"""Chat RAG (RF-03 / RF-06).

Semana 2.5 - Adenda 1
---------------------
La vista web del asistente se construyo antes que el motor RAG. Este endpoint
existe para que la interfaz sea real y verificable, con el **contrato final**
(``respuesta`` + ``fuentes`` + ``modelo``). En la Semana 5 solo se reemplaza el
cuerpo por la llamada a ``vector_search`` + ``llm_service``: la ruta, el esquema
y el frontend no cambian.

Mientras tanto responde con un aviso claro en lugar de inventar productos, que
es justo lo que el sistema debe evitar (RNF-03, anti-alucinacion).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import usuario_actual
from app.core.logging import registrar_evento
from app.schemas.rag_schema import PreguntaChat, RespuestaChat

logger = logging.getLogger("ferreteria.rag_chat")

router = APIRouter(prefix="/rag", tags=["Chat RAG"])

MODELO_PROVISIONAL = "provisional-semana-2.5"

RESPUESTA_PROVISIONAL = (
    "El asistente todavía no consulta el catálogo: la búsqueda semántica se "
    "habilita en la Semana 5 del proyecto, junto con el modelo de lenguaje. "
    "Su pregunta quedó registrada y esta interfaz ya funciona de punta a punta; "
    "solo falta el motor que la responde."
)

AVISO_PROVISIONAL = (
    "Motor provisional. No se muestra ningún producto porque el catálogo aún "
    "no se ha vectorizado."
)


@router.get(
    "/estado",
    summary="Disponibilidad del motor RAG",
)
def estado(usuario: dict[str, Any] = Depends(usuario_actual)) -> dict:
    """Informa si el motor RAG real ya esta disponible."""
    return {
        "disponible": False,
        "modelo": MODELO_PROVISIONAL,
        "semana": 5,
        "detalle": "Busqueda vectorial y generacion de respuestas pendientes",
    }


@router.post(
    "/chat",
    response_model=RespuestaChat,
    summary="Consultar al asistente de inventario",
)
def chat(
    datos: PreguntaChat,
    request: Request,
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> RespuestaChat:
    """Recibe la pregunta y devuelve la respuesta con sus fuentes.

    Autenticado: el chat requiere sesion y queda auditado (RF-05.1).
    """
    registrar_evento(
        request,
        f"consulta al asistente: {datos.pregunta[:120]}",
        id_usuario=usuario["id"],
    )

    return RespuestaChat(
        respuesta=RESPUESTA_PROVISIONAL,
        fuentes=[],
        modelo=MODELO_PROVISIONAL,
        aviso=AVISO_PROVISIONAL,
    )
