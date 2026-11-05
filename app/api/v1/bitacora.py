"""Visor de la bitacora de auditoria (RF-05.2).

La tabla es inmutable: esta ruta solo consulta. No existen endpoints para
modificar ni eliminar eventos, y la base rechaza esas operaciones.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import requiere_permiso
from app.models import bitacora as bitacora_model
from app.schemas.bitacora_schema import EventoBitacora

router = APIRouter(prefix="/bitacora", tags=["Bitacora"])

CAPACIDAD = "bitacora:consultar"


@router.get(
    "",
    response_model=list[EventoBitacora],
    summary="Consultar la bitacora de auditoria",
    responses={400: {"description": "Rango de fechas invalido"}},
)
def consultar(
    desde: date | None = Query(default=None, description="Fecha inicial (AAAA-MM-DD)"),
    hasta: date | None = Query(default=None, description="Fecha final (AAAA-MM-DD)"),
    usuario: str | None = Query(
        default=None, max_length=50, description="Usuario o parte de su nombre"
    ),
    id_usuario: int | None = Query(default=None, ge=1),
    modulo: str | None = Query(default=None, max_length=50),
    ip: str | None = Query(default=None, max_length=45),
    limite: int = Query(default=200, ge=1, le=500),
    _: dict[str, Any] = Depends(requiere_permiso(CAPACIDAD)),
) -> list[dict[str, Any]]:
    """Devuelve los eventos mas recientes que cumplen los filtros."""
    if desde and hasta and desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha inicial no puede ser posterior a la fecha final",
        )

    return bitacora_model.listar(
        desde=desde,
        hasta=hasta,
        usuario=usuario,
        id_usuario=id_usuario,
        modulo=modulo,
        ip=ip,
        limite=limite,
    )


@router.get(
    "/modulos",
    response_model=list[str],
    summary="Modulos registrados en la bitacora",
)
def modulos(
    _: dict[str, Any] = Depends(requiere_permiso(CAPACIDAD)),
) -> list[str]:
    """Alimenta el filtro de modulo del visor."""
    return bitacora_model.modulos()
