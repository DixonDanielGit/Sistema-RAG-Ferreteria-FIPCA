"""Rutas de consulta e ingesta del catalogo."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import requiere_admin, usuario_actual
from app.core.logging import registrar_evento
from app.models import inventario as inventario_model
from app.schemas.inventario_schema import ArchivoIngesta, RespuestaIngesta
from app.services import etl_service

router = APIRouter(prefix="/inventario", tags=["Inventario"])


@router.get(
    "/archivos",
    response_model=list[ArchivoIngesta],
    summary="Listar archivos de catalogo recientes",
)
def archivos(
    limite: int = Query(default=100, ge=1, le=100),
    _: dict[str, Any] = Depends(usuario_actual),
) -> list[dict[str, Any]]:
    """Permite a usuarios autenticados revisar el estado de las ingestas."""
    return inventario_model.listar_archivos(limite)


@router.post(
    "/ingesta",
    response_model=RespuestaIngesta,
    summary="Cargar catalogos de productos",
    responses={
        400: {"description": "Lote vacio o con demasiados archivos"},
        403: {"description": "Solo administradores pueden cargar catalogos"},
    },
)
async def ingesta(
    request: Request,
    archivos: list[UploadFile] | None = File(
        default=None, description="PDF, XLSX, DOCX o TXT"
    ),
    usuario: dict[str, Any] = Depends(requiere_admin),
) -> RespuestaIngesta:
    """Procesa cada archivo del lote independientemente."""
    if not archivos or len(archivos) > etl_service.MAX_ARCHIVOS_INGESTA:
        raise HTTPException(
            status_code=400,
            detail=f"El lote debe contener entre 1 y {etl_service.MAX_ARCHIVOS_INGESTA} archivos",
        )

    resultados: list[dict[str, Any]] = []
    for archivo in archivos:
        try:
            contenido = await archivo.read(etl_service.MAX_ARCHIVO_BYTES + 1)
            resultado = await run_in_threadpool(
                etl_service.procesar_archivo,
                archivo.filename or "",
                contenido,
                usuario["id"],
            )
            resultados.append(resultado)
        finally:
            await archivo.close()

    registrar_evento(
        request,
        f"ingesta de catalogo: {len(resultados)} archivos",
        id_usuario=usuario["id"],
    )
    estados = [resultado["estado"] for resultado in resultados]
    return RespuestaIngesta(
        resultados=resultados,
        total_archivos=len(resultados),
        archivos_ok=estados.count("ok"),
        archivos_parciales=estados.count("parcial"),
        archivos_error=estados.count("error"),
        archivos_rechazados=estados.count("rechazado"),
    )