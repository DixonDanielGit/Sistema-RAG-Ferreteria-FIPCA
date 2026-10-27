"""Registro de eventos y middleware de auditoria (RF-05.1).

Dos piezas:

* ``registrar_evento``: lo llaman las rutas para dejar constancia de una accion
  concreta (login, alta de usuario, cambio de precio...).
* ``AuditoriaMiddleware``: intercepta cada peticion a la API y escribe en la
  bitacora los eventos marcados por la ruta o, si no hubo evento explicito,
  cualquier respuesta de error (4xx/5xx).

La escritura en la bitacora nunca debe tumbar una peticion: si la base de
auditoria falla, el error se registra en el log del proceso y la respuesta
sigue su curso.
"""

from __future__ import annotations

import logging
import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings

logger = logging.getLogger("ferreteria.auditoria")

PREFIJO_API = "/api/v1"

MODULOS = {
    "auth": "auth",
    "inventario": "inventario",
    "bitacora": "bitacora",
    "chat": "rag_chat",
}

# Rutas que no se auditan: ruido sin valor forense.
RUTAS_EXCLUIDAS = {"/", "/salud", "/favicon.ico", "/docs", "/redoc", "/openapi.json"}

_PATRON_IPS = re.compile(r"^[0-9a-fA-F:.]{3,45}$")


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Formato unico de logs para toda la aplicacion."""
    if logging.getLogger().handlers:
        logging.getLogger().setLevel(nivel)
        return

    logging.basicConfig(
        level=nivel,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Librerias externas: solo avisos relevantes.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def modulo_de_ruta(ruta: str) -> str | None:
    """Deduce el modulo auditado a partir de la ruta de la API."""
    if not ruta.startswith(PREFIJO_API):
        return None
    resto = ruta[len(PREFIJO_API) :].strip("/").split("/")[0]
    if not resto:
        return None
    return MODULOS.get(resto, resto[:50])


def ip_de_peticion(request: Request) -> str:
    """IP de origen, respetando X-Forwarded-For solo si hay proxy de confianza."""
    config = get_settings()

    if config.confiar_en_proxy:
        reenviada = request.headers.get("x-forwarded-for", "")
        if reenviada:
            primera = reenviada.split(",")[0].strip()
            if _PATRON_IPS.match(primera):
                return primera

    cliente = request.client
    return cliente.host if cliente and cliente.host else "desconocida"


def registrar_evento(request: Request, accion: str, id_usuario: int | None = None) -> None:
    """Marca un evento para que el middleware lo escriba al terminar la peticion."""
    request.state.auditoria = {"accion": accion, "id_usuario": id_usuario}


class AuditoriaMiddleware(BaseHTTPMiddleware):
    """Escribe en la bitacora los eventos de la API."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.auditoria = None
        request.state.usuario_auditado = None
        request.state.peticion_inicio = None

        modulo = modulo_de_ruta(request.url.path)

        try:
            respuesta = await call_next(request)
        except Exception:
            if modulo:
                self._escribir(
                    request,
                    id_usuario=getattr(request.state, "usuario_auditado", None),
                    accion=f"error no controlado en {request.method} {request.url.path}",
                    modulo=modulo,
                )
            raise

        if modulo and request.url.path not in RUTAS_EXCLUIDAS:
            evento = getattr(request.state, "auditoria", None)

            if evento:
                self._escribir(
                    request,
                    id_usuario=evento.get("id_usuario"),
                    accion=evento.get("accion", ""),
                    modulo=modulo,
                )
            elif respuesta.status_code >= 400:
                self._escribir(
                    request,
                    id_usuario=getattr(request.state, "usuario_auditado", None),
                    accion=(
                        f"{request.method} {request.url.path} respondio "
                        f"{respuesta.status_code}"
                    ),
                    modulo=modulo,
                )

        return respuesta

    @staticmethod
    def _escribir(
        request: Request, *, id_usuario: int | None, accion: str, modulo: str
    ) -> None:
        if not accion.strip():
            return

        try:
            # Importacion diferida: evita cargar el pool antes de que la app
            # este configurada (y permite probar el middleware sin base).
            from app.models import bitacora

            bitacora.registrar(
                id_usuario=id_usuario,
                accion=accion,
                ip=ip_de_peticion(request),
                modulo=modulo,
            )
        except Exception as exc:  # noqa: BLE001 - la auditoria no debe romper la API
            logger.error("No se pudo escribir en la bitacora: %s", exc)
