"""Rutas HTML de la interfaz web (Adenda 1).

Separadas de la API a proposito: ``/api/v1/*`` devuelve JSON para clientes y
estas rutas devuelven plantillas Jinja2 para el navegador. La logica de negocio
sigue viviendo en ``app/services`` y ``app/models``; aqui solo se decide que se
muestra y a donde se redirige.

Ninguna plantilla recibe el JWT: viaja en la cookie ``HttpOnly`` y el navegador
la envia sola. El token CSRF si se expone en el HTML, porque su proposito es
justamente que el JS lo reenvie en la cabecera.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api import deps
from app.config import get_settings
from app.core import sesion
from app.core.security import generar_token_csrf

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
DIRECTORIO_PLANTILLAS = RAIZ_PROYECTO / "templates"

plantillas = Jinja2Templates(directory=str(DIRECTORIO_PLANTILLAS))

router = APIRouter(tags=["Interfaz web"], include_in_schema=False)

# Vigencia de la cookie CSRF: la de la sesion, con un minimo util.
MINUTOS_COOKIE_CSRF = 30


def _contexto(request: Request, usuario: dict[str, Any] | None = None) -> dict[str, Any]:
    """Datos comunes a todas las plantillas."""
    config = get_settings()
    return {
        "request": request,
        "empresa": config.empresa,
        "sistema": config.nombre,
        "version": config.version,
        "expiracion_sesion_minutos": config.jwt_expiracion_minutos,
        "usuario": usuario,
    }


def _html(
    request: Request,
    plantilla: str,
    contexto: dict[str, Any],
    *,
    estado: int = 200,
) -> HTMLResponse:
    """Renderiza y garantiza que exista la cookie CSRF."""
    csrf = sesion.token_csrf(request)
    nueva = not csrf
    if nueva:
        csrf = generar_token_csrf()

    respuesta = plantillas.TemplateResponse(
        request=request,
        name=plantilla,
        context={**contexto, "csrf": csrf},
        status_code=estado,
    )

    if nueva:
        config = get_settings()
        respuesta.set_cookie(
            config.cookie_csrf,
            csrf,
            max_age=MINUTOS_COOKIE_CSRF * 60,
            httponly=False,
            secure=config.cookie_segura,
            samesite="lax",
            path="/",
        )

    return respuesta


def _redirigir(destino: str, *, estado: int = 303) -> RedirectResponse:
    return RedirectResponse(url=destino, status_code=estado)


def _sesion(request: Request) -> dict[str, Any] | None:
    return deps.usuario_de_cookie(request)


@router.get("/login", response_class=HTMLResponse, summary="Formulario de acceso")
def login(request: Request) -> HTMLResponse:
    if _sesion(request):
        return _redirigir("/dashboard")
    return _html(request, "login.html", _contexto(request))


@router.get("/recuperar", response_class=HTMLResponse, summary="Pedir enlace de recuperacion")
def recuperar(request: Request) -> HTMLResponse:
    if _sesion(request):
        return _redirigir("/dashboard")
    return _html(request, "recuperar.html", _contexto(request))


@router.get("/restablecer", response_class=HTMLResponse, summary="Nueva contrasena")
def restablecer(request: Request) -> HTMLResponse:
    token = request.query_params.get("token", "")[:200]
    contexto = {**_contexto(request), "token": token}
    return _html(request, "restablecer.html", contexto)


@router.get("/dashboard", response_class=HTMLResponse, summary="Panel principal")
def dashboard(request: Request) -> HTMLResponse:
    usuario = _sesion(request)
    if usuario is None:
        return _redirigir("/login")
    return _html(request, "dashboard.html", _contexto(request, usuario))


@router.get("/chat", response_class=HTMLResponse, summary="Asistente de inventario")
def chat(request: Request) -> HTMLResponse:
    usuario = _sesion(request)
    if usuario is None:
        return _redirigir("/login")
    return _html(request, "chat_rag.html", _contexto(request, usuario))


@router.get("/usuarios", response_class=HTMLResponse, summary="Gestion de usuarios")
def usuarios(request: Request) -> HTMLResponse:
    usuario = _sesion(request)
    if usuario is None:
        return _redirigir("/login")
    if usuario["rol"] != "admin":
        return _redirigir("/dashboard")
    return _html(request, "usuarios.html", _contexto(request, usuario))


@router.get("/perfil", response_class=HTMLResponse, summary="Perfil personal")
def perfil(request: Request) -> HTMLResponse:
    usuario = _sesion(request)
    if usuario is None:
        return _redirigir("/login")
    return _html(request, "perfil.html", _contexto(request, usuario))


@router.get("/configuracion", response_class=HTMLResponse, summary="Configuracion del sistema")
def configuracion(request: Request) -> HTMLResponse:
    usuario = _sesion(request)
    if usuario is None:
        return _redirigir("/login")
    return _html(request, "configuracion.html", _contexto(request, usuario))


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> HTMLResponse:
    return HTMLResponse(status_code=204)
