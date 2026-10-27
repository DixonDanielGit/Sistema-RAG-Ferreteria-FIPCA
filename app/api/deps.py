"""Dependencias compartidas de la API: autenticacion y autorizacion por rol."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.jwt import TokenInvalido, decodificar_token
from app.models import usuario as usuario_model

esquema_bearer = HTTPBearer(
    auto_error=False,
    description="Token JWT obtenido en /api/v1/auth/login",
)

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales invalidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def _resolver_usuario(
    request: Request, credenciales: HTTPAuthorizationCredentials | None
) -> dict[str, Any]:
    if credenciales is None or not credenciales.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de acceso",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decodificar_token(credenciales.credentials)
    except TokenInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # La cuenta se relee de la base: un token valido no basta si el usuario
    # fue desactivado o eliminado despues de emitirlo.
    usuario = usuario_model.buscar_por_id(claims["id_usuario"])
    if usuario is None:
        raise CREDENCIALES_INVALIDAS

    if not usuario["activo"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva",
        )

    request.state.usuario_auditado = usuario["id"]
    return usuario


def usuario_actual(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
) -> dict[str, Any]:
    """Devuelve la cuenta autenticada o lanza 401."""
    return _resolver_usuario(request, credenciales)


def requiere_admin(
    usuario: dict[str, Any] = Depends(usuario_actual),
) -> dict[str, Any]:
    """Exige rol administrador (RF-01.2)."""
    if usuario.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol administrador",
        )
    return usuario


def puede_registrar(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
) -> dict[str, Any] | None:
    """Autoriza el alta de usuarios.

    * Si el sistema no tiene ninguna cuenta, permite crear la primera
      (administrador inicial) sin token: es el arranque del sistema.
    * En cualquier otro caso exige un token con rol administrador.
    """
    if usuario_model.contar() == 0:
        return None

    usuario = _resolver_usuario(request, credenciales)
    if usuario.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol administrador para registrar usuarios",
        )
    return usuario
