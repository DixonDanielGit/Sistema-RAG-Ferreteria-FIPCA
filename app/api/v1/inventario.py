"""Rutas de consulta, ingesta y eliminacion del catalogo."""

from __future__ import annotations

import json
import threading

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool

from app.api.deps import requiere_permiso, usuario_actual
from app.core.logging import registrar_evento
from app.models import inventario as inventario_model
from app.schemas.inventario_schema import (
    ArchivoIngesta,
    EstadoVectorizacion,
    MetadatosCatalogo,
    RespuestaEliminacionArchivo,
    RespuestaEliminacionCatalogos,
    RespuestaIngesta,
    SolicitudEliminacionCatalogos,
)
from app.services import etl_service, vector_search

router = APIRouter(prefix="/inventario", tags=["Inventario"])

# Solo una ingesta a la vez: la subida automatica del cliente envia los
# archivos en secuencia, y este candado impide que dos lotes (de dos pestañas
# o de un cliente API) se procesen en paralelo y colapsen el servidor.
_cerradura_ingesta = threading.Lock()
_adaptador_metadatos = TypeAdapter(list[MetadatosCatalogo])


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


@router.get(
    "/vectorizacion",
    response_model=EstadoVectorizacion,
    summary="Cobertura del indice de busqueda",
)
def estado_vectorizacion(
    _: dict[str, Any] = Depends(usuario_actual),
) -> dict[str, Any]:
    """Productos del catalogo todavia sin embedding.

    Un producto sin vector no entra en la busqueda semantica, asi que el
    asistente no puede responder sobre el: el panel lo muestra para que la
    vectorizacion no se olvide despues de cada carga. `en_curso` indica si
    un lote automatico esta corriendo ahora para que el panel espere el
    resultado en lugar de mostrar un conteo viejo.
    """
    pendientes = inventario_model.contar_productos_sin_embedding()
    total = inventario_model.contar_productos_catalogo()
    return {
        "total": total,
        "pendientes": pendientes,
        "en_curso": vector_search.vectorizacion_en_curso(),
    }


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
    selecciones_precio: str | None = Form(default=None),
    metadatos_catalogo: str | None = Form(default=None),
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

    try:
        metadatos = _adaptador_metadatos.validate_json(metadatos_catalogo or "")
    except ValidationError as exc:
        etiquetas = {
            "proveedor": "nombre del proveedor",
            "vendedor": "nombre del vendedor",
            "telefono_vendedor": "telefono",
            "correo_vendedor": "correo",
            "moneda": "moneda",
            "nota_proveedor": "nota",
        }
        errores = []
        for error in exc.errors()[:5]:
            ubicacion = error.get("loc", ())
            indice = ubicacion[0] if ubicacion and isinstance(ubicacion[0], int) else None
            campo = ubicacion[-1] if ubicacion else None
            etiqueta = etiquetas.get(campo, "datos de cotizacion")
            mensaje = f"{etiqueta} invalido"
            if campo in ("proveedor", "vendedor") and error["type"] == "missing":
                mensaje = f"falta el {etiqueta}"
            if indice is not None:
                mensaje = f"Archivo {indice + 1}: {mensaje}"
            errores.append(mensaje)
        detalle = "Datos de cotizacion invalidos"
        if errores:
            detalle += ": " + "; ".join(errores)
        raise HTTPException(
            status_code=400,
            detail=detalle,
        ) from exc
    if len(metadatos) != len(archivos):
        raise HTTPException(
            status_code=400,
            detail="Debe indicar los datos del proveedor para cada archivo y en el mismo orden",
        )

    try:
        opciones = json.loads(selecciones_precio or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="La seleccion de precios no tiene un formato valido",
        ) from exc
    if not isinstance(opciones, dict) or any(
        not isinstance(clave, str)
        or not clave.isdecimal()
        or not isinstance(valor, int)
        or isinstance(valor, bool)
        or valor < 0
        for clave, valor in opciones.items()
    ):
        raise HTTPException(
            status_code=400,
            detail="La seleccion de precios no tiene un formato valido",
        )
    selecciones = {int(clave): valor for clave, valor in opciones.items()}

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
        for indice, archivo in enumerate(archivos):
            try:
                contenido = await archivo.read(etl_service.MAX_ARCHIVO_BYTES + 1)
                argumentos = (
                    archivo.filename or "",
                    contenido,
                    usuario["id"],
                )
                resultado = await run_in_threadpool(
                    etl_service.procesar_archivo,
                    *argumentos,
                    selecciones,
                    metadatos[indice].model_dump(),
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

    # La carga deja productos sin vector: se indexan en segundo plano para
    # que el panel de fuentes no quede marcando pendientes hasta que alguien
    # recuerde correr el script manual. Solo si algo se guardo de verdad.
    if any(estado in {"ok", "parcial"} for estado in estados):
        vector_search.lanzar_vectorizacion_automatica()

    return RespuestaIngesta(
        resultados=resultados,
        total_archivos=len(resultados),
        archivos_ok=estados.count("ok"),
        archivos_parciales=estados.count("parcial"),
        archivos_error=estados.count("error"),
        archivos_rechazados=estados.count("rechazado"),
    )


@router.post(
    "/previsualizacion",
    summary="Analizar un catalogo antes de guardarlo",
    responses={
        403: {"description": "Se requiere permiso para cargar catalogos"},
        422: {"description": "El archivo no contiene productos legibles"},
    },
)
async def previsualizacion(
    archivo: UploadFile = File(description="PDF, XLSX, DOCX o TXT"),
    selecciones_precio: str | None = Form(default=None),
    _: dict[str, Any] = Depends(requiere_permiso("catalogos:ingestar")),
) -> dict[str, Any]:
    """Analiza el archivo sin guardar el original ni modificar el inventario."""
    contenido = await archivo.read(etl_service.MAX_ARCHIVO_BYTES + 1)
    await archivo.close()
    try:
        opciones = json.loads(selecciones_precio or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="La seleccion de precios no tiene un formato valido",
        ) from exc
    if not isinstance(opciones, dict) or any(
        not isinstance(clave, str)
        or not clave.isdecimal()
        or not isinstance(valor, int)
        or isinstance(valor, bool)
        or valor < 0
        for clave, valor in opciones.items()
    ):
        raise HTTPException(
            status_code=400,
            detail="La seleccion de precios no tiene un formato valido",
        )
    try:
        return await run_in_threadpool(
            etl_service.previsualizar_archivo,
            archivo.filename or "",
            contenido,
            {int(clave): valor for clave, valor in opciones.items()},
        )
    except etl_service.ErrorIngesta as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    if resultado["eliminados"]:
        vector_search.lanzar_vectorizacion_automatica()
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
    vector_search.lanzar_vectorizacion_automatica()
    return resultado