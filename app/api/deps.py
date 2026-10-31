"""Dependencias compartidas de la API: autenticacion y autorizacion por rol.

Dos formas de presentar el token (Adenda 1):

* ``Authorization: Bearer <jwt>`` -> clientes de API (curl, Swagger, pruebas).
* cookie ``HttpOnly`` -> interfaz web, que asi nunca expone el token a
  JavaScript.

Cuando la autenticacion llega por cookie y el metodo cambia estado, se exige
ademas el token CSRF (ver :mod:`app.core.sesion`).
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.core import sesion
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

SIN_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Falta el token de acceso",
    headers={"WWW-Authenticate": "Bearer"},
)


def usuario_de_token(token: str) -> dict[str, Any]:
    """Valida el token y devuelve la cuenta vigente.

    La cuenta se relee de la base: un token bien firmado no basta si el usuario
    fue desactivado despues de emitirlo.
    """
    try:
        claims = decodificar_token(token)
    except TokenInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    usuario = usuario_model.buscar_por_id(claims["id_usuario"])
    if usuario is None:
        raise CREDENCIALES_INVALIDAS

    if not usuario["activo"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva",
        )

    return usuario


def usuario_de_cookie(request: Request) -> dict[str, Any] | None:
    """Cuenta autenticada por cookie, o ``None``. No lanza excepciones.

    Pensada para las rutas HTML, que redirigen al login en vez de devolver 401.
    """
    token, origen = sesion.leer_token(request)
    if not token or origen != sesion.ORIGEN_AUTENTICADO:
        return None

    try:
        usuario = usuario_de_token(token)
    except HTTPException:
        return None

    request.state.usuario_auditado = usuario["id"]
    return usuario


def _resolver_usuario(
    request: Request, credenciales: HTTPAuthorizationCredentials | None
) -> dict[str, Any]:
    token, origen = sesion.leer_token(
        request, credenciales.credentials if credenciales else None
    )

    if not token:
        raise SIN_TOKEN

    usuario = usuario_de_token(token)
    request.state.usuario_auditado = usuario["id"]

    # La cookie viaja sola: si el metodo cambia estado, hace falta el CSRF.
    if origen == sesion.ORIGEN_AUTENTICADO and request.method not in sesion.METODOS_SEGUROS:
        sesion.validar_csrf(request)

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


def requiere_permiso(clave: str):
    """Construye una dependencia que exige una capacidad vigente de la cuenta."""

    def verificar(
        usuario: dict[str, Any] = Depends(usuario_actual),
    ) -> dict[str, Any]:
        if clave not in usuario.get("permisos", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para realizar esta operacion",
            )
        return usuario

    return verificar


def puede_registrar(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
) -> dict[str, Any] | None:
    """Autoriza el alta de usuarios.

    * Si el sistema no tiene ninguna cuenta, permite crear la primera
      (administrador inicial) sin token: es el arranque del sistema.
    * En cualquier otro caso exige la capacidad de gestionar usuarios.
    """
    if usuario_model.contar() == 0:
        return None

    usuario = _resolver_usuario(request, credenciales)
    if "usuarios:gestionar" not in usuario.get("permisos", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere permiso para registrar usuarios",
        )
    return usuario


def es_sesion_web(request: Request) -> bool:
    """True si la peticion se autentico por cookie (no por cabecera)."""
    _, origen = sesion.leer_token(request)
    return origen == sesion.ORIGEN_AUTENTICADO and bool(
        request.cookies.get(get_settings().cookie_nombre)
    )
