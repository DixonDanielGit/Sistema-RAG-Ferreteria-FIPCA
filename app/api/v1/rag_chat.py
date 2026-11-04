"""Chat RAG (RF-03 / RF-06)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import usuario_actual
from app.config import get_settings
from app.core.logging import registrar_evento
from app.schemas.rag_schema import (
    FuenteProducto,
    PreguntaChat,
    RespuestaChat,
)
from app.services import llm_service, vector_search
from app.services.embedding_service import ErrorEmbedding
from app.services.llm_service import ErrorLLM

logger = logging.getLogger("ferreteria.rag_chat")

router = APIRouter(prefix="/rag", tags=["Chat RAG"])

MODELO_SIN_CONFIGURAR = "sin-configurar"


@router.get(
    "/estado",
    summary="Disponibilidad del motor RAG",
)
def estado(usuario: dict[str, Any] = Depends(usuario_actual)) -> dict:
    """Informa si el proveedor generativo esta configurado."""
    config = get_settings()
    return {
        "disponible": config.llm_configurado,
        "modelo": config.llm_modelo or MODELO_SIN_CONFIGURAR,
        "semana": 4,
        "detalle": (
            "Proveedor configurado; la disponibilidad se confirma al consultar"
            if config.llm_configurado
            else "Configure el proveedor de lenguaje para habilitar respuestas"
        ),
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
    """Recupera productos, genera una respuesta y devuelve sus fuentes."""
    registrar_evento(
        request,
        f"consulta al asistente: {datos.pregunta[:120]}",
        id_usuario=usuario["id"],
    )

    try:
        productos = vector_search.buscar_productos(datos.pregunta)
    except ErrorEmbedding as exc:
        logger.warning("No se pudo vectorizar la consulta: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="No se pudo preparar la busqueda semantica",
        ) from exc

    try:
        resultado = llm_service.generar_respuesta(datos.pregunta, productos)
    except ErrorLLM as exc:
        logger.warning("No se pudo generar la respuesta RAG: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="No se pudo generar una respuesta con el proveedor configurado",
        ) from exc

    fuentes = [
        FuenteProducto(
            codigo=producto.get("codigo"),
            nombre=producto["nombre"],
            marca=producto.get("marca"),
            precio=producto["precio"],
            stock=producto["stock"],
            categoria=producto.get("categoria"),
        )
        for producto in productos
    ]
    return RespuestaChat(
        respuesta=resultado.respuesta,
        fuentes=fuentes,
        modelo=resultado.modelo,
        aviso=resultado.aviso,
    )
