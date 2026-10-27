"""Sesion web: cookies y proteccion CSRF (Adenda 1).

La interfaz web no guarda el JWT en JavaScript. El login deja el token en una
cookie ``HttpOnly`` (inaccesible para scripts) y ``SameSite=Lax``, de modo que
un XSS no puede robarlo.

Como la cookie viaja sola en cada peticion, los metodos que cambian estado
necesitan una defensa extra contra CSRF: el patron *double submit*. El servidor
publica una cookie ``csrf_token`` legible por JavaScript y el frontend la
reenvia en la cabecera ``X-CSRF-Token``. Un sitio externo puede provocar la
peticion, pero no puede leer la cookie para copiar la cabecera.

Nada de esto afecta a los clientes de la API (curl, Swagger, pruebas): si la
autenticacion llega por ``Authorization: Bearer`` no se exige CSRF, porque una
cabecera personalizada no se adjunta de forma automatica.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response, status

from app.config import Settings, get_settings
from app.core.security import generar_token_csrf, tokens_coinciden

CABECERA_CSRF = "X-CSRF-Token"
METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
ORIGEN_AUTENTICADO = "cookie"


def leer_token(request: Request, token_cabecera: str | None = None) -> tuple[str | None, str]:
    """Devuelve ``(token, origen)`` con origen ``header``, ``cookie`` o vacio."""
    if token_cabecera:
        return token_cabecera, "header"
    cookie = request.cookies.get(get_settings().cookie_nombre)
    if cookie:
        return cookie, ORIGEN_AUTENTICADO
    return None, ""


def publicar_cookies_sesion(
    respuesta: Response,
    token: str,
    segundos: int,
    *,
    settings: Settings | None = None,
) -> str:
    """Deja la cookie de sesion y la de CSRF. Devuelve el token CSRF."""
    config = settings or get_settings()
    csrf = generar_token_csrf()

    respuesta.set_cookie(
        config.cookie_nombre,
        token,
        max_age=segundos,
        httponly=True,
        secure=config.cookie_segura,
        samesite="lax",
        path="/",
    )
    respuesta.set_cookie(
        config.cookie_csrf,
        csrf,
        max_age=segundos,
        httponly=False,
        secure=config.cookie_segura,
        samesite="lax",
        path="/",
    )
    return csrf


def borrar_cookies_sesion(
    respuesta: Response, *, settings: Settings | None = None
) -> None:
    """Elimina ambas cookies (cierre de sesion)."""
    config = settings or get_settings()
    for nombre in (config.cookie_nombre, config.cookie_csrf):
        respuesta.delete_cookie(
            nombre,
            path="/",
            secure=config.cookie_segura,
            httponly=nombre == config.cookie_nombre,
            samesite="lax",
        )


def token_csrf(request: Request, *, settings: Settings | None = None) -> str:
    """Token CSRF vigente de la peticion (cadena vacia si no hay)."""
    config = settings or get_settings()
    return request.cookies.get(config.cookie_csrf, "")


def origen_confiable(request: Request, settings: Settings | None = None) -> bool:
    """Comprueba que el ``Origin`` de la peticion pertenece al sistema."""
    config = settings or get_settings()
    origen = request.headers.get("origin")
    if not origen:
        return True  # sin Origin no hay navegador cross-site implicado

    partes = urlsplit(origen)
    origen_netloc = f"{partes.scheme}://{partes.netloc}"
    permitidos = {config.url_base, *config.cors_origenes}
    return origen_netloc in permitidos


def validar_csrf(request: Request, *, settings: Settings | None = None) -> None:
    """Exige cabecera CSRF valida y origen confiable en metodos de escritura."""
    config = settings or get_settings()
    cookie = request.cookies.get(config.cookie_csrf, "")
    enviado = request.headers.get(CABECERA_CSRF, "")

    if not cookie or not enviado or not tokens_coinciden(cookie, enviado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF ausente o invalido; recargue la pagina",
        )

    if not origen_confiable(request, config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origen de la peticion no permitido",
        )
