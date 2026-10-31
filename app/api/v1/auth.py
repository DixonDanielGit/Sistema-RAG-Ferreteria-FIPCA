"""Endpoints de autenticacion (RF-01).

Rutas:

* ``POST /api/v1/auth/login``      -> entrega un JWT con expiracion.
* ``POST /api/v1/auth/register``   -> alta de cuentas (administrador).
* ``GET  /api/v1/auth/me``         -> datos de la cuenta autenticada.
* ``POST /api/v1/auth/logout``     -> cierra la sesion del lado del cliente.
* ``GET  /api/v1/auth/roles``      -> catalogo de roles (administrador).
* ``POST /api/v1/auth/recuperar``  -> enlace de recuperacion por correo (Adenda 1).
* ``POST /api/v1/auth/restablecer``-> nueva contrasena con el token del correo.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from psycopg2 import Error as ErrorPostgres
from psycopg2.errors import UniqueViolation
from starlette.responses import Response as StarletteResponse

from app.api.deps import puede_registrar, requiere_admin, requiere_permiso, usuario_actual
from app.core import sesion
from app.core.jwt import crear_token
from app.core.logging import ip_de_peticion, registrar_evento
from app.core.security import (
    gastar_tiempo_como_si_existiera,
    hash_password,
    necesita_rehash,
    verify_password,
)
from app.models import usuario as usuario_model
from app.db.session import BaseDeDatosNoDisponible, consultar_uno
from app.schemas.usuario_schema import (
    EstadoCuentaActualizar,
    LoginRequest,
    MensajeRespuesta,
    PerfilActualizar,
    PermisoSalida,
    RecuperarPasswordRequest,
    RestablecerPasswordRequest,
    RolActualizar,
    RolCrear,
    RolConfiguracionActualizar,
    RolSalida,
    TokenRespuesta,
    UsuarioAdminActualizar,
    UsuarioRegistro,
    UsuarioSalida,
)
from app.services import etl_service, perfil_service, recuperacion_service

logger = logging.getLogger("ferreteria.auth")

router = APIRouter(prefix="/auth", tags=["Autenticacion"])

# Mensaje unico para no revelar si el usuario existe (evita enumeracion).
MENSAJE_CREDENCIALES = "Usuario o contrasena incorrectos"


@router.post(
    "/login",
    response_model=TokenRespuesta,
    summary="Iniciar sesion",
    responses={
        401: {"description": "Credenciales invalidas"},
        403: {"description": "Cuenta inactiva"},
    },
)
def login(datos: LoginRequest, request: Request, respuesta: Response) -> TokenRespuesta:
    """Valida las credenciales y emite un token de acceso."""
    usuario = usuario_model.buscar_por_identificador(datos.identificador)

    if usuario is None:
        # Se verifica igual contra un hash ficticio para que la respuesta
        # tarde lo mismo que con una cuenta real.
        gastar_tiempo_como_si_existiera(datos.password)
        registrar_evento(
            request,
            f"login fallido: identificador inexistente ({datos.identificador[:80]})",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MENSAJE_CREDENCIALES,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario["activo"]:
        registrar_evento(
            request,
            f"login rechazado: cuenta inactiva ({usuario['usuario']})",
            id_usuario=usuario["id"],
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva; contacte al administrador",
        )

    if not verify_password(datos.password, usuario["password"]):
        registrar_evento(
            request,
            f"login fallido: contrasena incorrecta ({usuario['usuario']})",
            id_usuario=usuario["id"],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MENSAJE_CREDENCIALES,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Si el hash se genero con parametros antiguos, se actualiza sin que el
    # usuario lo note (migracion transparente del costo de hashing).
    if necesita_rehash(usuario["password"]):
        try:
            usuario_model.actualizar_password(usuario["id"], hash_password(datos.password))
        except ErrorPostgres as exc:
            logger.warning("No se pudo actualizar el hash de %s: %s", usuario["usuario"], exc)

    token = crear_token(
        id_usuario=usuario["id"],
        usuario=usuario["usuario"],
        rol=usuario["rol"],
    )

    registrar_evento(request, f"login exitoso ({usuario['usuario']})", id_usuario=usuario["id"])

    # Adenda 1: la interfaz web usa la cookie; el cuerpo con el token se
    # mantiene intacto para los clientes de API.
    sesion.publicar_cookies_sesion(respuesta, token.token, token.segundos_restantes)

    return TokenRespuesta(
        access_token=token.token,
        expira_en=token.segundos_restantes,
        expira_en_utc=token.expira_en,
        usuario=UsuarioSalida(**usuario),
    )


@router.post(
    "/register",
    response_model=UsuarioSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar usuario",
    responses={
        403: {"description": "Requiere rol administrador"},
        409: {"description": "Usuario, correo o cedula ya registrados"},
    },
)
def register(
    datos: UsuarioRegistro,
    request: Request,
    autorizador: dict[str, Any] | None = Depends(puede_registrar),
) -> UsuarioSalida:
    """Da de alta una cuenta nueva."""
    es_primera_cuenta = autorizador is None

    if es_primera_cuenta and datos.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La primera cuenta del sistema debe tener rol administrador",
        )
    if autorizador and autorizador["rol"] != "admin" and datos.rol == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede asignar el rol admin",
        )

    duplicados = usuario_model.conflictos(datos.usuario, datos.correo, datos.cedula)
    if duplicados:
        registrar_evento(
            request,
            f"alta rechazada: datos duplicados en {', '.join(duplicados)}",
            id_usuario=autorizador["id"] if autorizador else None,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cuenta con ese {', '.join(duplicados)}",
        )

    id_rol = usuario_model.id_de_rol(datos.rol)
    if id_rol is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rol indicado no existe",
        )

    try:
        creado = usuario_model.crear(
            id_rol=id_rol,
            cedula=datos.cedula,
            nombre=datos.nombre,
            apellido=datos.apellido,
            usuario=datos.usuario,
            password_hash=hash_password(datos.password),
            correo=datos.correo,
        )
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usuario, correo o cedula ya registrados",
        ) from exc

    registrar_evento(
        request,
        f"alta de usuario ({datos.usuario}) con rol {datos.rol}",
        id_usuario=autorizador["id"] if autorizador else creado["id"],
    )

    return UsuarioSalida(**creado)


@router.get(
    "/me",
    response_model=UsuarioSalida,
    summary="Datos de la cuenta autenticada",
)
def me(usuario: dict[str, Any] = Depends(usuario_actual)) -> UsuarioSalida:
    return UsuarioSalida(**usuario)


@router.get(
    "/usuarios",
    response_model=list[UsuarioSalida],
    summary="Listar usuarios (administrador)",
)
def listar_usuarios(
    usuario: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> list[UsuarioSalida]:
    return [UsuarioSalida(**fila) for fila in usuario_model.listar_usuarios()]


@router.put(
    "/usuarios/{id_usuario}",
    response_model=UsuarioSalida,
    summary="Actualizar datos y rol de una cuenta (administrador)",
    responses={
        403: {"description": "Requiere rol administrador"},
        409: {"description": "Datos duplicados o ultimo administrador activo"},
    },
)
def actualizar_usuario_admin(
    id_usuario: int,
    datos: UsuarioAdminActualizar,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> UsuarioSalida:
    if administrador["rol"] != "admin" and datos.rol == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede asignar el rol admin",
        )
    duplicados = usuario_model.conflictos(
        datos.usuario,
        datos.correo,
        datos.cedula,
        id_excluir=id_usuario,
    )
    if duplicados:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe otra cuenta con ese {', '.join(duplicados)}",
        )

    try:
        resultado = usuario_model.actualizar_usuario_admin(
            id_usuario,
            cedula=datos.cedula,
            nombre=datos.nombre,
            apellido=datos.apellido,
            usuario=datos.usuario,
            correo=datos.correo,
            rol=datos.rol,
        )
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=409,
            detail="Usuario, correo o cedula ya registrados",
        ) from exc

    if resultado == "no_encontrado":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if resultado == "rol_invalido":
        raise HTTPException(status_code=400, detail="El rol indicado no existe")
    if resultado == "ultimo_admin":
        raise HTTPException(
            status_code=409,
            detail="No se puede retirar el rol al ultimo administrador activo",
        )

    actualizado = usuario_model.buscar_por_id(id_usuario)
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(
        request,
        f"datos y rol de usuario {id_usuario} actualizados por administrador",
        id_usuario=administrador["id"],
    )
    return UsuarioSalida(**actualizado)


async def _normalizar_archivo_imagen(archivo: UploadFile) -> bytes:
    try:
        contenido = await archivo.read(perfil_service.MAX_IMAGEN_PERFIL_BYTES + 1)
    finally:
        await archivo.close()

    if len(contenido) > perfil_service.MAX_IMAGEN_PERFIL_BYTES:
        raise HTTPException(status_code=413, detail="La imagen supera el limite de 2 MB")

    try:
        return perfil_service.normalizar_imagen_perfil(contenido)
    except perfil_service.ImagenPerfilInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _respuesta_imagen_usuario(
    id_usuario: int, detalle_si_no_existe: str = "El usuario no tiene una imagen"
) -> StarletteResponse:
    imagen = usuario_model.obtener_imagen(id_usuario)
    if imagen is None:
        raise HTTPException(status_code=404, detail=detalle_si_no_existe)
    return StarletteResponse(
        content=imagen,
        media_type="image/webp",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get(
    "/usuarios/{id_usuario}/imagen",
    summary="Obtener la imagen de una cuenta (administrador)",
)
def obtener_imagen_usuario_admin(
    id_usuario: int,
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> StarletteResponse:
    return _respuesta_imagen_usuario(id_usuario)


@router.post(
    "/usuarios/{id_usuario}/imagen",
    response_model=MensajeRespuesta,
    summary="Actualizar la imagen de una cuenta (administrador)",
)
async def actualizar_imagen_usuario_admin(
    id_usuario: int,
    request: Request,
    archivo: UploadFile = File(...),
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> MensajeRespuesta:
    imagen = await _normalizar_archivo_imagen(archivo)
    if not usuario_model.guardar_imagen(id_usuario, imagen):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(
        request,
        f"imagen de usuario {id_usuario} actualizada por administrador",
        id_usuario=administrador["id"],
    )
    return MensajeRespuesta(mensaje="Imagen de usuario actualizada")


@router.delete(
    "/usuarios/{id_usuario}/imagen",
    response_model=MensajeRespuesta,
    summary="Eliminar la imagen de una cuenta (administrador)",
)
def eliminar_imagen_usuario_admin(
    id_usuario: int,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> MensajeRespuesta:
    if not usuario_model.eliminar_imagen(id_usuario):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(
        request,
        f"imagen de usuario {id_usuario} eliminada por administrador",
        id_usuario=administrador["id"],
    )
    return MensajeRespuesta(mensaje="Imagen de usuario eliminada")


@router.delete(
    "/usuarios/{id_usuario}",
    response_model=MensajeRespuesta,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    summary="No se permiten eliminaciones fisicas de cuentas",
    responses={403: {"description": "Requiere rol administrador"}},
)
def eliminar_usuario_no_permitido(
    id_usuario: int,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> MensajeRespuesta:
    """Mantiene la regla de negocio: las cuentas se desactivan, no se borran."""
    registrar_evento(
        request,
        f"se intento eliminar la cuenta {id_usuario} mediante DELETE",
        id_usuario=administrador["id"],
    )
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Las cuentas no se eliminan fisicamente; desactivalas en su lugar",
    )


@router.patch(
    "/usuarios/{id_usuario}/rol",
    response_model=UsuarioSalida,
    summary="Cambiar el rol de una cuenta",
    responses={403: {"description": "Requiere rol administrador"}, 409: {"description": "Ultimo administrador activo"}},
)
def cambiar_rol(
    id_usuario: int,
    datos: RolActualizar,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> UsuarioSalida:
    if administrador["rol"] != "admin" and datos.rol == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede asignar el rol admin",
        )
    resultado = usuario_model.actualizar_rol_admin(id_usuario, datos.rol)
    if resultado == "no_encontrado":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if resultado == "rol_invalido":
        raise HTTPException(status_code=400, detail="El rol indicado no existe")
    if resultado == "ultimo_admin":
        raise HTTPException(
            status_code=409,
            detail="No se puede retirar el rol al ultimo administrador activo",
        )

    actualizado = usuario_model.buscar_por_id(id_usuario)
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(
        request,
        f"rol de usuario {id_usuario} actualizado a {datos.rol}",
        id_usuario=administrador["id"],
    )
    return UsuarioSalida(**actualizado)


@router.patch(
    "/usuarios/{id_usuario}/estado",
    response_model=UsuarioSalida,
    summary="Activar o desactivar una cuenta",
    responses={403: {"description": "Requiere rol administrador"}, 409: {"description": "Ultimo administrador activo"}},
)
def cambiar_estado_usuario(
    id_usuario: int,
    datos: EstadoCuentaActualizar,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar")),
) -> UsuarioSalida:
    resultado = usuario_model.actualizar_estado_admin(id_usuario, datos.activo)
    if resultado == "no_encontrado":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if resultado == "ultimo_admin":
        raise HTTPException(
            status_code=409,
            detail="No se puede desactivar al ultimo administrador activo",
        )

    actualizado = usuario_model.buscar_por_id(id_usuario)
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(
        request,
        f"usuario {id_usuario} {'activado' if datos.activo else 'desactivado'}",
        id_usuario=administrador["id"],
    )
    return UsuarioSalida(**actualizado)


@router.put(
    "/me",
    response_model=UsuarioSalida,
    summary="Actualizar el perfil de la cuenta autenticada",
    responses={409: {"description": "Usuario, correo o cedula ya registrados"}},
)
def actualizar_perfil(
    datos: PerfilActualizar,
    request: Request,
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> UsuarioSalida:
    duplicados = usuario_model.conflictos(
        datos.usuario,
        datos.correo,
        datos.cedula,
        id_excluir=usuario["id"],
    )
    if duplicados:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe otra cuenta con ese {', '.join(duplicados)}",
        )

    try:
        actualizado = usuario_model.actualizar_perfil(
            usuario["id"],
            cedula=datos.cedula,
            nombre=datos.nombre,
            apellido=datos.apellido,
            usuario=datos.usuario,
            correo=datos.correo,
        )
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=409,
            detail="Usuario, correo o cedula ya registrados",
        ) from exc

    if actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    registrar_evento(request, f"perfil actualizado ({usuario['id']})", id_usuario=usuario["id"])
    return UsuarioSalida(**actualizado)


@router.get("/me/imagen", summary="Obtener la imagen de perfil")
def obtener_imagen_perfil(
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> StarletteResponse:
    return _respuesta_imagen_usuario(
        usuario["id"], detalle_si_no_existe="El perfil no tiene una imagen"
    )


@router.post(
    "/me/imagen",
    response_model=MensajeRespuesta,
    summary="Actualizar la imagen de perfil",
)
async def actualizar_imagen_perfil(
    request: Request,
    archivo: UploadFile = File(...),
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> MensajeRespuesta:
    imagen = await _normalizar_archivo_imagen(archivo)
    if not usuario_model.guardar_imagen(usuario["id"], imagen):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(request, f"imagen de perfil actualizada ({usuario['id']})", id_usuario=usuario["id"])
    return MensajeRespuesta(mensaje="Imagen de perfil actualizada")


@router.delete(
    "/me/imagen",
    response_model=MensajeRespuesta,
    summary="Eliminar la imagen de perfil",
)
def eliminar_imagen_perfil(
    request: Request,
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> MensajeRespuesta:
    if not usuario_model.eliminar_imagen(usuario["id"]):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    registrar_evento(request, f"imagen de perfil eliminada ({usuario['id']})", id_usuario=usuario["id"])
    return MensajeRespuesta(mensaje="Imagen de perfil eliminada")


@router.get(
    "/configuracion/admin",
    summary="Consultar estado de servicios y limites (administrador)",
)
def configuracion_admin(
    usuario: dict[str, Any] = Depends(requiere_permiso("configuracion:diagnostico")),
) -> dict[str, Any]:
    estados: dict[str, str] = {}
    for nombre, es_rag in (("ferreteria_rag", True), ("ferreteria_usuarios", False)):
        try:
            consultar_uno("SELECT 1 AS ok", rag=es_rag)
            estados[nombre] = "operativa"
        except (BaseDeDatosNoDisponible, ErrorPostgres) as exc:
            logger.warning("Estado no disponible para %s: %s", nombre, exc)
            estados[nombre] = "no disponible"

    return {
        "bases": estados,
        "ingesta": {
            "formatos": sorted(etl_service.EXTENSIONES_PERMITIDAS),
            "max_archivo_mb": etl_service.MAX_ARCHIVO_MB,
            "max_archivos": etl_service.MAX_ARCHIVOS_INGESTA,
            "max_filas_archivo": etl_service.MAX_FILAS_ARCHIVO,
            "max_paginas_pdf": etl_service.MAX_PAGINAS_PDF,
        },
        "imagen_perfil_max_mb": perfil_service.MAX_IMAGEN_PERFIL_BYTES // (1024 * 1024),
    }


@router.post(
    "/logout",
    response_model=MensajeRespuesta,
    summary="Cerrar sesion",
)
def logout(
    request: Request,
    respuesta: Response,
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> MensajeRespuesta:
    """Registra el cierre de sesion.

    El token es autocontenido: el cliente debe descartarlo. La expiracion del
    JWT acota el tiempo maximo de una sesion olvidada (RF-01.3).
    """
    sesion.borrar_cookies_sesion(respuesta)
    registrar_evento(request, f"cierre de sesion ({usuario['usuario']})", id_usuario=usuario["id"])
    return MensajeRespuesta(mensaje="Sesion cerrada correctamente")


@router.get(
    "/roles",
    response_model=list[RolSalida],
    summary="Listar roles disponibles para administracion de cuentas",
)
def roles(usuario: dict[str, Any] = Depends(requiere_permiso("usuarios:gestionar"))) -> list[RolSalida]:
    return [RolSalida(**fila) for fila in usuario_model.listar_roles()]


@router.get(
    "/roles/permisos",
    response_model=list[PermisoSalida],
    summary="Listar capacidades configurables (administrador)",
)
def capacidades(
    usuario: dict[str, Any] = Depends(requiere_admin),
) -> list[PermisoSalida]:
    return [PermisoSalida(**fila) for fila in usuario_model.listar_permisos()]


@router.post(
    "/roles",
    response_model=RolSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un rol (administrador)",
)
def crear_rol(
    datos: RolCrear,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_admin),
) -> RolSalida:
    try:
        id_rol = usuario_model.crear_rol(datos.nombre, datos.descripcion, datos.permisos)
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre") from exc

    registrar_evento(
        request,
        f"rol {datos.nombre} creado con {len(datos.permisos)} capacidades",
        id_usuario=administrador["id"],
    )
    creado = next(
        (fila for fila in usuario_model.listar_roles() if fila["id_rol"] == id_rol),
        None,
    )
    if creado is None:
        logger.error("No se pudo recuperar el rol recien creado: %s", id_rol)
        raise HTTPException(status_code=500, detail="No se pudo recuperar el rol creado")
    return RolSalida(**creado)


@router.put(
    "/roles/{id_rol}",
    response_model=RolSalida,
    summary="Actualizar un rol (administrador)",
)
def actualizar_rol(
    id_rol: int,
    datos: RolConfiguracionActualizar,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_admin),
) -> RolSalida:
    try:
        resultado = usuario_model.actualizar_rol(
            id_rol, datos.nombre, datos.descripcion, datos.permisos
        )
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre") from exc

    if resultado == "no_encontrado":
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if resultado == "protegido":
        raise HTTPException(status_code=409, detail="El rol admin esta protegido")

    registrar_evento(
        request,
        f"rol {id_rol} actualizado con {len(datos.permisos)} capacidades",
        id_usuario=administrador["id"],
    )
    actualizado = next(
        (fila for fila in usuario_model.listar_roles() if fila["id_rol"] == id_rol),
        None,
    )
    if actualizado is None:
        logger.error("No se pudo recuperar el rol actualizado: %s", id_rol)
        raise HTTPException(status_code=500, detail="No se pudo recuperar el rol actualizado")
    return RolSalida(**actualizado)


@router.delete(
    "/roles/{id_rol}",
    response_model=MensajeRespuesta,
    summary="Eliminar un rol sin cuentas asignadas (administrador)",
)
def eliminar_rol(
    id_rol: int,
    request: Request,
    administrador: dict[str, Any] = Depends(requiere_admin),
) -> MensajeRespuesta:
    resultado = usuario_model.eliminar_rol(id_rol)
    if resultado == "no_encontrado":
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if resultado == "protegido":
        raise HTTPException(status_code=409, detail="El rol admin esta protegido")
    if resultado == "asignado":
        raise HTTPException(status_code=409, detail="No se puede eliminar un rol con cuentas asignadas")

    registrar_evento(
        request,
        f"rol {id_rol} eliminado",
        id_usuario=administrador["id"],
    )
    return MensajeRespuesta(mensaje="Rol eliminado")


@router.post(
    "/recuperar",
    response_model=MensajeRespuesta,
    summary="Solicitar enlace de recuperacion de contrasena",
    responses={429: {"description": "Demasiadas solicitudes desde esta IP"}},
)
def recuperar(
    datos: RecuperarPasswordRequest,
    request: Request,
) -> MensajeRespuesta:
    """Envia un enlace de un solo uso, exista o no la cuenta.

    La respuesta es identica en todos los casos para no revelar que correos
    estan registrados.
    """
    try:
        resultado = recuperacion_service.solicitar(
            datos.correo,
            ip=ip_de_peticion(request),
        )
    except recuperacion_service.DemasiadosIntentos as exc:
        registrar_evento(request, "recuperacion bloqueada: demasiados intentos")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espere unos minutos antes de reintentar.",
            headers={"Retry-After": "900"},
        ) from exc

    if resultado.modo == "omitido":
        registrar_evento(request, "solicitud de recuperacion sin cuenta asociada")
    else:
        registrar_evento(request, f"solicitud de recuperacion enviada ({resultado.modo})")

    return MensajeRespuesta(mensaje=resultado.mensaje)


@router.post(
    "/restablecer",
    response_model=MensajeRespuesta,
    summary="Restablecer contrasena con el token del correo",
    responses={400: {"description": "Enlace invalido, vencido o ya utilizado"}},
)
def restablecer(
    datos: RestablecerPasswordRequest,
    request: Request,
    respuesta: Response,
) -> MensajeRespuesta:
    """Consume el token y guarda la contrasena nueva."""
    try:
        cuenta = recuperacion_service.restablecer(datos.token, datos.password)
    except recuperacion_service.RecuperacionInvalida as exc:
        registrar_evento(request, "restablecimiento rechazado: enlace invalido")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Cualquier sesion abierta con la contrasena anterior deja de servir en el
    # navegador: se borran las cookies de este equipo.
    sesion.borrar_cookies_sesion(respuesta)
    registrar_evento(
        request,
        f"contrasena restablecida por enlace ({cuenta['usuario']})",
        id_usuario=cuenta["id"],
    )
    return MensajeRespuesta(
        mensaje="Contrasena actualizada. Ya puede iniciar sesion con su nueva clave."
    )
