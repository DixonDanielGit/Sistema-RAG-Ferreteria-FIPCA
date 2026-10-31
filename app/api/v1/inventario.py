"""Rutas de consulta, ingesta y eliminacion del catalogo."""

from __future__ import annotations

import threading

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from starlette.concurrency import run_in_threadpool

from app.api.deps import requiere_permiso, usuario_actual
from app.core.logging import registrar_evento
from app.models import inventario as inventario_model
from app.schemas.inventario_schema import (
    ArchivoIngesta,
    RespuestaEliminacionArchivo,
    RespuestaEliminacionCatalogos,
    RespuestaIngesta,
    SolicitudEliminacionCatalogos,
)
from app.services import etl_service

router = APIRouter(prefix="/inventario", tags=["Inventario"])

# Solo una ingesta a la vez: la subida automatica del cliente envia los
# archivos en secuencia, y este candado impide que dos lotes (de dos pestañas
# o de un cliente API) se procesen en paralelo y colapsen el servidor.
_cerradura_ingesta = threading.Lock()


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
        409: {
            "description": "Ya hay otra carga de catalogo en proceso"
        },
    },
)
async def ingesta(
    request: Request,
    archivos: list[UploadFile] | None = File(
        default=None, description="PDF, XLSX, DOCX o TXT"
    ),
    usuario: dict[str, Any] = Depends(requiere_permiso("catalogos:ingestar")),
) -> RespuestaIngesta:
    """Procesa cada archivo del lote independientemente.

    Solo se acepta una ingesta a la vez: si otra esta en marcha la peticion
    se rechaza con 409 para no sobrecargar el servidor.
    """
    if not archivos or len(archivos) > etl_service.MAX_ARCHIVOS_INGESTA:
        raise HTTPException(
            status_code=400,
            detail=f"El lote debe contener entre 1 y {etl_service.MAX_ARCHIVOS_INGESTA} archivos",
        )

    if not _cerradura_ingesta.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail=(
                "Ya hay una carga de catalogo en proceso; "
                "espere a que termine para subir mas archivos"
            ),
        )

    try:
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
    finally:
        _cerradura_ingesta.release()
    return RespuestaIngesta(
        resultados=resultados,
        total_archivos=len(resultados),
        archivos_ok=estados.count("ok"),
        archivos_parciales=estados.count("parcial"),
        archivos_error=estados.count("error"),
        archivos_rechazados=estados.count("rechazado"),
    )


@router.post(
    "/archivos/eliminacion-multiple",
    response_model=RespuestaEliminacionCatalogos,
    summary="Eliminar varios catalogos seleccionados",
    responses={
        403: {"description": "Solo administradores pueden eliminar catalogos"},
    },
)
async def eliminar_archivos(
    request: Request,
    solicitud: SolicitudEliminacionCatalogos,
    usuario: dict[str, Any] = Depends(requiere_permiso("catalogos:eliminar")),
) -> dict[str, Any]:
    """Elimina los catalogos existentes seleccionados y reporta los ausentes."""
    resultado = await run_in_threadpool(
        etl_service.eliminar_catalogos_completos,
        solicitud.ids_archivos,
    )
    for catalogo in resultado["eliminados"]:
        registrar_evento(
            request,
            (
                f"eliminacion de catalogo: {catalogo['nombre']} "
                f"({catalogo['productos_eliminados']} productos)"
            ),
            id_usuario=usuario["id"],
        )
    return resultado


@router.delete(
    "/archivos/{id_archivo}",
    response_model=RespuestaEliminacionArchivo,
    summary="Eliminar un catalogo y sus datos asociados",
    responses={
        403: {"description": "Solo administradores pueden eliminar catalogos"},
        404: {"description": "El catalogo no existe o ya fue eliminado"},
    },
)
async def eliminar_archivo(
    request: Request,
    *,
    id_archivo: int = Path(ge=1, description="Identificador del archivo subido"),
    usuario: dict[str, Any] = Depends(requiere_permiso("catalogos:eliminar")),
) -> dict[str, Any]:
    """Retira un catalogo cargado, procesado o no, y todo lo que provino de el.

    La eliminacion es transaccional: los productos asociados al documento
    (con sus vectores) se quitan junto con el registro del archivo y el
    original deja de existir en disco.
    """
    resultado = await run_in_threadpool(
        etl_service.eliminar_catalogo_completo, id_archivo
    )
    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="El catalogo solicitado no existe o ya fue eliminado",
        )

    registrar_evento(
        request,
        (
            f"eliminacion de catalogo: {resultado['nombre']} "
            f"({resultado['productos_eliminados']} productos)"
        ),
        id_usuario=usuario["id"],
    )
    return resultado