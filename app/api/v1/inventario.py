"""Rutas de consulta, ingesta y eliminacion del catalogo."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path as PathLib

from typing import Any, Literal

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
from app.config import get_settings

logger = logging.getLogger("ferreteria.api.inventario")
from app.core.logging import registrar_evento
from app.models import inventario as inventario_model
from app.schemas.inventario_schema import (
    ArchivoIngesta,
    LIMITE_DEFECTO_BUSQUEDA,
    LIMITE_MAXIMO_BUSQUEDA,
    LONGITUD_MAXIMA_BUSQUEDA,
    LONGITUD_MINIMA_BUSQUEDA,
    MetadatosCatalogo,
    DetalleProducto,
    RespuestaExtraccion,
    RespuestaObservacion,
    RespuestaEliminacionArchivo,
    RespuestaEliminacionCatalogos,
    RespuestaIngesta,
    ResultadoCatalogo,
    ResultadoBusqueda,
    SolicitudEliminacionCatalogos,
    SolicitudObservacionCatalogo,
    SolicitudObservacionProducto,
)
from app.services import etl_service

router = APIRouter(prefix="/inventario", tags=["Inventario"])

# Solo una ingesta a la vez: la subida automatica del cliente envia los
# archivos en secuencia, y este candado impide que dos lotes (de dos pestañas
# o de un cliente API) se procesen en paralelo y colapsen el servidor.
_cerradura_ingesta = threading.Lock()
_adaptador_metadatos = TypeAdapter(list[MetadatosCatalogo])


def _leer_selecciones_precio(valor: str | None) -> dict[int, int]:
    """Convierte el JSON de seleccion de precios en ``{hoja: columna}``.

    Las tres rutas que leen catalogos (ingesta, previsualizacion y la prueba de
    extraccion) reciben la misma seleccion, asi que la validacion vive aqui.
    """
    try:
        opciones = json.loads(valor or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="La seleccion de precios no tiene un formato valido",
        ) from exc
    if not isinstance(opciones, dict) or any(
        not isinstance(clave, str)
        or not clave.isdecimal()
        or not isinstance(valor_columna, int)
        or isinstance(valor_columna, bool)
        or valor_columna < 0
        for clave, valor_columna in opciones.items()
    ):
        raise HTTPException(
            status_code=400,
            detail="La seleccion de precios no tiene un formato valido",
        )
    return {int(clave): valor_columna for clave, valor_columna in opciones.items()}


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
    "/busqueda",
    response_model=ResultadoBusqueda,
    summary="Buscar productos en el catalogo (Full-Text Search)",
    responses={
        401: {"description": "Sesion no valida"},
        422: {"description": "Consulta vacia o demasiado corta"},
    },
)
def busqueda(
    request: Request,
    consulta: str = Query(
        min_length=LONGITUD_MINIMA_BUSQUEDA,
        max_length=LONGITUD_MAXIMA_BUSQUEDA,
        description="Nombre, codigo, marca, descripcion, proveedor o categoria",
    ),
    limite: int = Query(
        default=LIMITE_DEFECTO_BUSQUEDA,
        ge=1,
        le=LIMITE_MAXIMO_BUSQUEDA,
        description="Maximo de productos por pagina",
    ),
    pagina: int = Query(default=1, ge=1, description="Pagina de resultados"),
    ordenar_por: Literal[
        "codigo", "nombre", "proveedor", "precio", "stock"
    ] | None = Query(
        default=None,
        description="Columna para ordenar los resultados",
    ),
    direccion: Literal["asc", "desc"] = Query(
        default="asc",
        description="Direccion del ordenamiento",
    ),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> ResultadoBusqueda:
    """Busqueda local con Full-Text Search de PostgreSQL (RF-03).

    La ruta no llama a ningun modelo de IA: `tsvector` en espanol y `ILIKE`
    como respaldo responden en milisegundos sobre el catalogo completo. Que
    no haya coincidencias es un resultado valido, no un error, y el buscador
    jamas inventa productos.
    """
    limpio = " ".join(consulta.split())
    if len(limpio) < LONGITUD_MINIMA_BUSQUEDA:
        raise HTTPException(
            status_code=422,
            detail=(
                f"La busqueda debe tener al menos "
                f"{LONGITUD_MINIMA_BUSQUEDA} caracteres"
            ),
        )

    filas, total = inventario_model.buscar_productos_fulltext(
        limpio,
        limite,
        (pagina - 1) * limite,
        ordenar_por,
        direccion,
    )
    registrar_evento(
        request,
        f"busqueda de catalogo: {limpio}",
        id_usuario=usuario["id"],
    )
    return ResultadoBusqueda(
        consulta=limpio,
        total=total,
        pagina=pagina,
        limite=limite,
        productos=filas,
    )


@router.get(
    "/catalogo",
    response_model=ResultadoCatalogo,
    summary="Listar productos activos del catalogo",
)
def catalogo(
    request: Request,
    pagina: int = Query(default=1, ge=1, description="Pagina del catalogo"),
    limite: int = Query(
        default=LIMITE_DEFECTO_BUSQUEDA,
        ge=1,
        le=LIMITE_MAXIMO_BUSQUEDA,
        description="Maximo de productos por pagina",
    ),
    ordenar_por: Literal[
        "codigo", "nombre", "proveedor", "precio", "stock"
    ] | None = Query(
        default=None,
        description="Columna para ordenar los resultados",
    ),
    direccion: Literal["asc", "desc"] = Query(
        default="asc",
        description="Direccion del ordenamiento",
    ),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> ResultadoCatalogo:
    """Lista el catalogo activo sin ejecutar modelos de IA."""
    filas, total = inventario_model.listar_productos_catalogo(
        limite, (pagina - 1) * limite, ordenar_por, direccion
    )
    registrar_evento(
        request,
        f"consulta de catalogo completo: pagina {pagina}",
        id_usuario=usuario["id"],
    )
    return ResultadoCatalogo(
        total=total, pagina=pagina, limite=limite, productos=filas
    )


@router.get(
    "/productos/{id_producto}",
    response_model=DetalleProducto,
    summary="Consultar detalle comercial y origen de un producto",
    responses={404: {"description": "Producto no encontrado"}},
)
def detalle_producto(
    request: Request,
    id_producto: int = Path(ge=1),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> DetalleProducto:
    """Devuelve datos del producto y la trazabilidad de su catalogo."""
    detalle = inventario_model.obtener_detalle_producto(id_producto)
    if detalle is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    registrar_evento(
        request,
        f"consulta de detalle de producto: {id_producto}",
        id_usuario=usuario["id"],
    )
    return DetalleProducto(**detalle)


@router.patch(
    "/productos/{id_producto}/observacion",
    response_model=RespuestaObservacion,
    summary="Actualizar la observacion comercial de un producto",
    responses={404: {"description": "Producto no encontrado"}},
)
def actualizar_observacion_producto(
    request: Request,
    solicitud: SolicitudObservacionProducto,
    id_producto: int = Path(ge=1),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> dict[str, Any]:
    resultado = inventario_model.actualizar_observacion_producto(
        id_producto, solicitud.observacion
    )
    if resultado is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    registrar_evento(
        request,
        f"actualizacion de observacion comercial de producto: {id_producto}",
        id_usuario=usuario["id"],
    )
    return resultado


@router.delete(
    "/productos/{id_producto}/observacion",
    status_code=204,
    summary="Eliminar la observacion comercial de un producto",
    responses={404: {"description": "Producto u observacion no encontrados"}},
)
def eliminar_observacion_producto(
    request: Request,
    id_producto: int = Path(ge=1),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> None:
    resultado = inventario_model.eliminar_observacion_producto(id_producto)
    if resultado is None:
        raise HTTPException(
            status_code=404, detail="Producto u observacion no encontrados"
        )
    registrar_evento(
        request,
        f"eliminacion de observacion comercial de producto: {id_producto}",
        id_usuario=usuario["id"],
    )


@router.patch(
    "/catalogos/{id_archivo}/observacion",
    response_model=RespuestaObservacion,
    summary="Actualizar la observacion comercial compartida de un catalogo",
    responses={404: {"description": "Catalogo no encontrado"}},
)
def actualizar_observacion_catalogo(
    request: Request,
    solicitud: SolicitudObservacionCatalogo,
    id_archivo: int = Path(ge=1),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> dict[str, Any]:
    resultado = inventario_model.actualizar_observacion_catalogo(
        id_archivo, solicitud.observacion
    )
    if resultado is None:
        raise HTTPException(status_code=404, detail="Catalogo no encontrado")
    registrar_evento(
        request,
        f"actualizacion de observacion comercial de catalogo: {id_archivo}",
        id_usuario=usuario["id"],
    )
    return resultado


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
    token: str | None = Form(
        default=None, description="Token de previsualizacion (ingesta diferida)"
    ),
    selecciones_precio: str | None = Form(default=None),
    metadatos_catalogo: str | None = Form(default=None),
    usuario: dict[str, Any] = Depends(requiere_permiso("catalogos:ingestar")),
) -> RespuestaIngesta:
    """Procesa cada archivo del lote independientemente.

    Soporta dos modos:
    * **Lote tradicional:** subir archivos directamente via ``archivos``.
    * **Ingesta diferida:** pasar un ``token`` obtenido de ``/previsualizacion``.
      En este modo no se suben archivos; los productos ya estan extraidos.

    Solo se acepta una ingesta a la vez: si otra esta en marcha la peticion
    se rechaza con 409 para no sobrecargar el servidor.
    """
    # ── Rama ingesta diferida (token-based) ──────────────
    if archivos is None and token:
        return await _ingestar_por_token(request, token, metadatos_catalogo, usuario)

    # ── Rama tradicional (file-based) ────────────────────
    if not archivos or len(archivos) > etl_service.MAX_ARCHIVOS_INGESTA:
        raise HTTPException(
            status_code=400,
            detail=f"El lote debe contener entre 1 y {etl_service.MAX_ARCHIVOS_INGESTA} archivos",
        )
    try:
            metadatos = _adaptador_metadatos.validate_json(metadatos_catalogo or "[]")
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

    metadatos_archivos = []
    for indice, archivo in enumerate(archivos):
        datos = {
            **metadatos[indice].model_dump(),
            "proveedor": etl_service.nombre_proveedor_desde_archivo(
                archivo.filename or ""
            ),
        }
        try:
            metadatos_archivos.append(MetadatosCatalogo.model_validate(datos))
        except ValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Archivo {indice + 1}: nombre de proveedor invalido",
            ) from exc

    selecciones = _leer_selecciones_precio(selecciones_precio)

    if not _cerradura_ingesta.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail=(
                "Ya hay una carga de catalogo en proceso; "
                "espere a que termine para subir mas archivos"
            ),
        )

    try:
        t_total = time.perf_counter()
        resultados: list[dict[str, Any]] = []
        for indice, archivo in enumerate(archivos):
            try:
                t_leer = time.perf_counter()
                contenido = await archivo.read(etl_service.MAX_ARCHIVO_BYTES + 1)
                t_leido = time.perf_counter()
                argumentos = (
                    archivo.filename or "",
                    contenido,
                    usuario["id"],
                )
                resultado = await run_in_threadpool(
                    etl_service.procesar_archivo,
                    *argumentos,
                    selecciones,
                    metadatos_archivos[indice].model_dump(),
                )
                t_hecho = time.perf_counter()
                logger.info(
                    "FASE0 /ingesta archivo[%d] nombre=%s tamano=%d lectura=%.3fs procesamiento=%.3fs estado=%s",
                    indice, archivo.filename, len(contenido),
                    t_leido - t_leer, t_hecho - t_leido,
                    resultado.get("estado", "desconocido"),
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
        t_final = time.perf_counter()
        logger.info(
            "FASE0 /ingesta lote completo=%d archivos duracion=%.3fs",
            len(resultados), t_final - t_total,
        )
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


async def _ingestar_por_token(
    request: Request,
    token: str,
    metadatos_json: str | None,
    usuario: dict[str, Any],
) -> RespuestaIngesta:
    """Ingesta diferida: lee el JSON pre-extraido y solo inserta."""
    # Buscar archivo pendiente por token
    archivo_db = inventario_model.archivo_por_token(token)
    if archivo_db is None:
        raise HTTPException(
            status_code=404,
            detail="Token no encontrado o la previsualizacion ya expiro",
        )

    id_archivo = archivo_db["id_archivo"]
    directorio = get_settings().uploads_dir.resolve()
    ruta_json = directorio / f"{token}.productos.json"

    if not ruta_json.is_file():
        raise HTTPException(
            status_code=422,
            detail="Los productos pre-extraidos no estan disponibles; vuelva a previsualizar el archivo",
        )

    # Leer productos del JSON
    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            productos = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Error al leer los productos pre-extraidos",
        ) from exc

    if not productos:
        raise HTTPException(
            status_code=422,
            detail="El archivo no contiene productos verificables",
        )

    # Procesar metadatos (proveedor, contacto)
    metadatos_dict: dict[str, Any] = {}
    if metadatos_json:
        try:
            meta_parsed = json.loads(metadatos_json)
            if isinstance(meta_parsed, dict):
                metadatos_dict = meta_parsed
        except json.JSONDecodeError:
            pass

    # Asegurar que el proveedor se resuelva al confirmar
    nombre_proveedor = metadatos_dict.get("proveedor") or etl_service.nombre_proveedor_desde_archivo(
        archivo_db["nombre"]
    )
    metadatos_dict["proveedor"] = nombre_proveedor

    try:
        metadatos_validados = MetadatosCatalogo.model_validate(metadatos_dict)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail="Datos de cotizacion invalidos",
        ) from exc

    metadatos_final = metadatos_validados.model_dump()

    # Actualizar la fila de archivos_subidos con el proveedor
    _actualizar_archivo_con_proveedor(id_archivo, metadatos_final)

    # Insertar productos (sin re-extraer)
    resultado = await run_in_threadpool(
        etl_service.procesar_archivo,
        archivo_db["nombre"],
        b"",  # contenido vacio, no se usa en modo pre-extraido
        usuario["id"],
        None,  # selecciones_precio
        metadatos_final,
        productos,
        id_archivo,
    )

    # Limpiar JSON del disco
    ruta_json.unlink(missing_ok=True)

    registrar_evento(
        request,
        f"ingesta diferida de catalogo: {archivo_db['nombre']} ({len(productos)} productos)",
        id_usuario=usuario["id"],
    )

    estado = resultado.get("estado", "error")
    return RespuestaIngesta(
        resultados=[resultado],
        total_archivos=1,
        archivos_ok=1 if estado == "ok" else 0,
        archivos_parciales=1 if estado == "parcial" else 0,
        archivos_error=1 if estado == "error" else 0,
        archivos_rechazados=1 if estado == "rechazado" else 0,
    )


def _actualizar_archivo_con_proveedor(
    id_archivo: int,
    metadatos: dict[str, Any],
) -> None:
    """Actualiza la fila de archivos_subidos con el proveedor al confirmar."""
    proveedor = metadatos.get("proveedor")
    vendedor = metadatos.get("vendedor")
    telefono = metadatos.get("telefono_vendedor")
    correo = metadatos.get("correo_vendedor")
    moneda = metadatos.get("moneda", "USD")

    with inventario_model.cursor_rag() as cursor:
        if proveedor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(LOWER(%s))::BIGINT)",
                (proveedor,),
            )
            cursor.execute(
                """
                SELECT id_proveedores
                  FROM proveedores
                 WHERE LOWER(nombre) = LOWER(%s)
                 ORDER BY id_proveedores
                 FOR UPDATE
                """,
                (proveedor,),
            )
            existentes = cursor.fetchall()
            if existentes:
                id_proveedor = existentes[0]["id_proveedores"]
                cursor.execute(
                    """
                    UPDATE proveedores
                       SET vendedor = %s,
                           telefono_vendedor = COALESCE(NULLIF(%s, ''), telefono_vendedor),
                           correo_vendedor = COALESCE(NULLIF(%s, ''), correo_vendedor),
                           moneda = %s,
                           actualizado_en = NOW()
                     WHERE id_proveedores = %s
                    """,
                    (vendedor, telefono, correo, moneda, id_proveedor),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO proveedores
                        (nombre, vendedor, telefono_vendedor, correo_vendedor, moneda)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_proveedores
                    """,
                    (proveedor, vendedor, telefono, correo, moneda),
                )
                id_proveedor = cursor.fetchone()["id_proveedores"]

        cursor.execute(
            """
            UPDATE archivos_subidos
               SET id_proveedor = COALESCE(%s, id_proveedor),
                   vendedor_nombre = %s,
                   vendedor_telefono = %s,
                   vendedor_correo = %s,
                   moneda = %s,
                   nota_proveedor = %s
             WHERE id_archivo = %s
            """,
            (
                id_proveedor if proveedor else None,
                vendedor,
                telefono,
                correo,
                moneda,
                metadatos.get("nota_proveedor"),
                id_archivo,
            ),
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
    usuario: dict[str, Any] = Depends(requiere_permiso("catalogos:ingestar")),
) -> dict[str, Any]:
    """Analiza el archivo y guarda el resultado para una ingesta diferida.

    El original se conserva en disco y los productos extraidos se escriben
    en un archivo JSON hermano. La ingesta posterior solo necesita el
    ``token`` devuelto para completar la operacion sin releer el catalogo.
    """
    t0 = time.perf_counter()
    contenido = await archivo.read(etl_service.MAX_ARCHIVO_BYTES + 1)
    t1 = time.perf_counter()
    await archivo.close()
    selecciones = _leer_selecciones_precio(selecciones_precio)
    token = uuid.uuid4().hex
    nombre_original = archivo.filename or "catalogo"
    extension = PathLib(nombre_original).suffix.lower()

    # Guardar el original en uploads/
    directorio = get_settings().uploads_dir
    directorio = directorio.resolve()
    directorio.mkdir(parents=True, exist_ok=True)
    ruta_original = directorio / f"{token}{extension}"
    ruta_json = directorio / f"{token}.productos.json"
    try:
        descriptor = os.open(ruta_original, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as archivo_orig:
            archivo_orig.write(contenido)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo") from exc

    try:
        resultado = await run_in_threadpool(
            etl_service.previsualizar_archivo,
            nombre_original,
            contenido,
            selecciones,
            str(ruta_json),
        )
        t2 = time.perf_counter()
        logger.info(
            "FASE0 /previsualizacion nombre=%s tamano=%d token=%s lectura=%.3fs procesamiento=%.3fs",
            nombre_original, len(contenido), token, t1 - t0, t2 - t1,
        )
    except etl_service.ErrorIngesta as exc:
        ruta_original.unlink(missing_ok=True)
        ruta_json.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        ruta_original.unlink(missing_ok=True)
        ruta_json.unlink(missing_ok=True)
        raise

    # Crear registro pendiente en archivos_subidos (sin proveedor aun)
    try:
        import hashlib
        hash_sha256 = hashlib.sha256(contenido).hexdigest()
        archivo_db = inventario_model.crear_archivo(
            nombre=nombre_original,
            tipo=extension.lstrip(".") or "desconocido",
            ruta=token + extension,  # nombre relativo
            hash_sha256=hash_sha256,
            tamano_bytes=len(contenido),
            id_usuario=usuario["id"],
            token_confirmacion=token,
            crear_proveedor=False,
        )
    except Exception as exc:
        ruta_original.unlink(missing_ok=True)
        ruta_json.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="No se pudo registrar la previsualizacion") from exc

    resultado["token"] = token
    resultado["id_archivo"] = archivo_db["id_archivo"]
    return resultado


@router.delete(
    "/previsualizacion/{token}",
    summary="Cancelar una previsualizacion pendiente",
    responses={
        404: {"description": "Token no encontrado o ya no esta pendiente"},
    },
)
async def cancelar_previsualizacion(
    token: str = Path(description="Token UUID de la previsualizacion"),
    usuario: dict[str, Any] = Depends(requiere_permiso("catalogos:ingestar")),
) -> dict[str, str]:
    """Cancela una previsualizacion pendiente y libera los recursos.

    Marca el archivo como ``rechazado`` y elimina tanto el original como
    el JSON de productos del disco.
    """
    archivo = inventario_model.archivo_por_token(token)
    if archivo is None:
        raise HTTPException(
            status_code=404,
            detail="Token no encontrado o la previsualizacion ya no esta pendiente",
        )

    # Marcar como rechazado
    inventario_model.eliminar_archivo_por_token(token)

    # Eliminar archivos del disco
    directorio = get_settings().uploads_dir.resolve()
    extension = PathLib(archivo["nombre"]).suffix.lower()
    for nombre_archivo in (f"{token}{extension}", f"{token}.productos.json"):
        ruta = directorio / nombre_archivo
        ruta.unlink(missing_ok=True)

    logger.info(
        "Previsualizacion cancelada token=%s id_archivo=%d usuario=%s",
        token, archivo["id_archivo"], usuario.get("id"),
    )
    return {"estado": "cancelado", "token": token}


@router.post(
    "/extraccion-prueba",
    response_model=RespuestaExtraccion,
    summary="Extraer productos de archivos sin guardar nada (prueba del buscador local)",
    responses={
        400: {"description": "Lote vacio o con demasiados archivos"},
        401: {"description": "Sesion no valida"},
    },
)
async def extraccion_prueba(
    archivos: list[UploadFile] | None = File(
        default=None, description="PDF, XLSX, DOCX o TXT"
    ),
    selecciones_precio: str | None = Form(default=None),
    _: dict[str, Any] = Depends(usuario_actual),
) -> RespuestaExtraccion:
    """Lee los archivos con librerias locales y devuelve lo extraido en JSON.

    Es el paso de verificacion del buscador local: permite comprobar que la
    extraccion (pypdf, pdfplumber, openpyxl y python-docx) esta trayendo bien
    codigo, nombre, marca, precio y descripcion **antes** de guardar algo. No
    escribe el original en ``uploads``, no crea el registro del archivo y no
    inserta productos ni ofertas, por lo que tampoco se escribe en la bitacora.

    Los campos que el archivo no trae se devuelven en ``null``.
    """
    if not archivos or len(archivos) > etl_service.MAX_ARCHIVOS_INGESTA:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El lote debe contener entre 1 y "
                f"{etl_service.MAX_ARCHIVOS_INGESTA} archivos"
            ),
        )
    selecciones = _leer_selecciones_precio(selecciones_precio)

    resultados: list[dict[str, Any]] = []
    for archivo in archivos:
        try:
            contenido = await archivo.read(etl_service.MAX_ARCHIVO_BYTES + 1)
            resultados.append(
                await run_in_threadpool(
                    etl_service.extraer_catalogo_en_memoria,
                    archivo.filename or "",
                    contenido,
                    selecciones,
                )
            )
        finally:
            await archivo.close()

    estados = [resultado["estado"] for resultado in resultados]
    return RespuestaExtraccion(
        resultados=resultados,
        total_archivos=len(resultados),
        archivos_ok=estados.count("ok"),
        archivos_parciales=estados.count("parcial"),
        archivos_error=estados.count("error"),
        archivos_pendientes=estados.count("pendiente"),
        archivos_rechazados=estados.count("rechazado"),
        productos_extraidos=sum(len(resultado["productos"]) for resultado in resultados),
        persistido=False,
        aviso=(
            "Respuesta de prueba: nada se guardo en la base de datos ni en "
            "disco. Revise los productos extraidos de cada archivo"
        ),
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
    se quitan junto con el registro del archivo y el original deja de existir
    en disco.
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