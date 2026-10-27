"""Generacion y validacion de JSON Web Tokens (RF-01.1, RF-01.3).

Se usa PyJWT con firma HS256 y un secreto de al menos 32 caracteres. El token
incluye la expiracion (``exp``), que es lo que implementa el cierre de sesion
automatico por inactividad: al vencer, el cliente debe volver a autenticarse.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import Settings, get_settings

TIPO_TOKEN = "access"


class TokenInvalido(Exception):
    """El token esta vencido, mal firmado o no es un token de acceso."""


@dataclass(frozen=True)
class TokenGenerado:
    """Resultado de emitir un token."""

    token: str
    expira_en: datetime
    segundos_restantes: int
    claims: dict


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def crear_token(
    id_usuario: int,
    usuario: str,
    rol: str,
    *,
    minutos: int | None = None,
    emitido_en: datetime | None = None,
    settings: Settings | None = None,
) -> TokenGenerado:
    """Emite un token de acceso firmado.

    ``emitido_en`` y ``minutos`` existen para poder probar los valores limite
    de expiracion sin depender del reloj real.
    """
    config = settings or get_settings()

    if not isinstance(id_usuario, int) or id_usuario <= 0:
        raise ValueError("id_usuario debe ser un entero positivo")

    if not usuario or not str(usuario).strip():
        raise ValueError("usuario no puede estar vacio")

    if not rol or not str(rol).strip():
        raise ValueError("rol no puede estar vacio")

    duracion = config.jwt_expiracion_minutos if minutos is None else int(minutos)
    if duracion <= 0:
        raise ValueError("La duracion del token debe ser mayor que cero minutos")

    if config.jwt_secret.strip() == "":
        raise ValueError("JWT_SECRET no esta configurado")

    emision = (emitido_en or _ahora()).replace(microsecond=0)
    expiracion = emision + timedelta(minutes=duracion)

    claims = {
        "sub": str(id_usuario),
        "usuario": str(usuario),
        "rol": str(rol),
        "tipo": TIPO_TOKEN,
        "iss": config.jwt_emisor,
        "iat": int(emision.timestamp()),
        "nbf": int(emision.timestamp()),
        "exp": int(expiracion.timestamp()),
        "jti": uuid.uuid4().hex,
    }

    token = pyjwt.encode(claims, config.jwt_secret, algorithm=config.jwt_algoritmo)

    return TokenGenerado(
        token=token,
        expira_en=expiracion,
        segundos_restantes=int((expiracion - _ahora()).total_seconds()),
        claims=claims,
    )


def decodificar_token(
    token: str,
    *,
    settings: Settings | None = None,
    leeway_segundos: int = 0,
) -> dict:
    """Valida la firma y la vigencia de un token y devuelve sus claims.

    Lanza ``TokenInvalido`` con un motivo en espanol ante cualquier problema.
    """
    config = settings or get_settings()

    if not token or not isinstance(token, str):
        raise TokenInvalido("Token ausente o con formato invalido")

    try:
        claims = pyjwt.decode(
            token,
            config.jwt_secret,
            algorithms=[config.jwt_algoritmo],
            issuer=config.jwt_emisor,
            leeway=leeway_segundos,
            options={
                "require": ["exp", "iat", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": False,
            },
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise TokenInvalido("La sesion expiro; vuelva a iniciar sesion") from exc
    except pyjwt.ImmatureSignatureError as exc:
        raise TokenInvalido("El token todavia no es valido") from exc
    except pyjwt.InvalidIssuerError as exc:
        raise TokenInvalido("El token no fue emitido por este sistema") from exc
    except pyjwt.InvalidAlgorithmError as exc:
        raise TokenInvalido("Algoritmo de firma no permitido") from exc
    except pyjwt.MissingRequiredClaimError as exc:
        raise TokenInvalido(f"Token incompleto: falta {exc.claim}") from exc
    except pyjwt.InvalidTokenError as exc:
        raise TokenInvalido("Token invalido o firma incorrecta") from exc

    if claims.get("tipo") != TIPO_TOKEN:
        raise TokenInvalido("El token no es de acceso")

    try:
        id_usuario = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenInvalido("Token sin identificador de usuario valido") from exc

    if id_usuario <= 0:
        raise TokenInvalido("Token con identificador de usuario invalido")

    claims["id_usuario"] = id_usuario
    return claims


def segundos_para_expirar(claims: dict) -> int:
    """Segundos que le quedan al token (0 si ya expiro)."""
    expiracion = int(claims.get("exp", 0))
    return max(0, expiracion - int(_ahora().timestamp()))
