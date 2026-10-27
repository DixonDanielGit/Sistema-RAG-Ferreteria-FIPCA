"""Endpoints de autenticacion (RF-01).

Rutas:

* ``POST /api/v1/auth/login``    -> entrega un JWT con expiracion.
* ``POST /api/v1/auth/register`` -> alta de cuentas (administrador).
* ``GET  /api/v1/auth/me``       -> datos de la cuenta autenticada.
* ``POST /api/v1/auth/logout``   -> cierra la sesion del lado del cliente.
* ``GET  /api/v1/auth/roles``    -> catalogo de roles (administrador).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg2 import Error as ErrorPostgres

from app.api.deps import puede_registrar, requiere_admin, usuario_actual
from app.core.jwt import crear_token
from app.core.logging import registrar_evento
from app.core.security import (
    gastar_tiempo_como_si_existiera,
    hash_password,
    necesita_rehash,
    verify_password,
)
from app.models import usuario as usuario_model
from app.schemas.usuario_schema import (
    LoginRequest,
    MensajeRespuesta,
    RolSalida,
    TokenRespuesta,
    UsuarioRegistro,
    UsuarioSalida,
)

logger = logging.getLogger("ferreteria.auth")

router = APIRouter(prefix="/auth", tags=["Autenticacion"])

# Mensaje unico para no revelar si el usuario existe (evita enumeracion).
MENSAJE_CREDENCIALES = "Usuario o contrasena incorrectos"


def _ip(request: Request) -> str:
    from app.core.logging import ip_de_peticion

    return ip_de_peticion(request)


@router.post(
    "/login",
    response_model=TokenRespuesta,
    summary="Iniciar sesion",
    responses={
        401: {"description": "Credenciales invalidas"},
        403: {"description": "Cuenta inactiva"},
    },
)
def login(datos: LoginRequest, request: Request) -> TokenRespuesta:
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

    creado = usuario_model.crear(
        id_rol=id_rol,
        cedula=datos.cedula,
        nombre=datos.nombre,
        apellido=datos.apellido,
        usuario=datos.usuario,
        password_hash=hash_password(datos.password),
        correo=datos.correo,
    )

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


@router.post(
    "/logout",
    response_model=MensajeRespuesta,
    summary="Cerrar sesion",
)
def logout(
    request: Request,
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> MensajeRespuesta:
    """Registra el cierre de sesion.

    El token es autocontenido: el cliente debe descartarlo. La expiracion del
    JWT acota el tiempo maximo de una sesion olvidada (RF-01.3).
    """
    registrar_evento(request, f"cierre de sesion ({usuario['usuario']})", id_usuario=usuario["id"])
    return MensajeRespuesta(mensaje="Sesion cerrada correctamente")


@router.get(
    "/roles",
    response_model=list[RolSalida],
    summary="Listar roles",
)
def roles(usuario: dict[str, Any] = Depends(requiere_admin)) -> list[RolSalida]:
    return [RolSalida(**fila) for fila in usuario_model.listar_roles()]
