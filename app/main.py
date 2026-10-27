"""Punto de entrada de la API (FastAPI).

Arranque en desarrollo:

    uvicorn app.main:app --reload

Documentacion interactiva: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.api_router import api_router
from app.config import get_settings
from app.core.logging import AuditoriaMiddleware, configurar_logging
from app.db.session import BaseDeDatosNoDisponible, cerrar_pools, consultar_uno

logger = logging.getLogger("ferreteria")

DIRECTORIO_ESTATICOS = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    config = get_settings()
    logger.info("%s v%s iniciando en entorno '%s'", config.nombre, config.version, config.entorno)
    yield
    cerrar_pools()
    logger.info("Conexiones cerradas; aplicacion detenida")


def crear_aplicacion() -> FastAPI:
    """Fabrica de la aplicacion (permite instanciarla en pruebas)."""
    config = get_settings()
    config.validar()
    configurar_logging()

    aplicacion = FastAPI(
        title=config.nombre,
        description=(
            f"API de {config.empresa}. Gestion de inventario, "
            "autenticacion por roles y auditoria."
        ),
        version=config.version,
        lifespan=ciclo_de_vida,
    )

    # El ultimo middleware agregado es el mas externo: la auditoria ve la
    # peticion ya validada por CORS.
    aplicacion.add_middleware(AuditoriaMiddleware)

    if config.cors_origenes:
        aplicacion.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origenes),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    aplicacion.include_router(api_router)

    if DIRECTORIO_ESTATICOS.is_dir():
        aplicacion.mount(
            "/static", StaticFiles(directory=str(DIRECTORIO_ESTATICOS)), name="static"
        )

    @aplicacion.exception_handler(BaseDeDatosNoDisponible)
    async def sin_base_de_datos(_: Request, exc: BaseDeDatosNoDisponible) -> JSONResponse:
        logger.error("Base de datos no disponible: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "Servicio temporalmente no disponible. Intente mas tarde."},
        )

    @aplicacion.get("/", tags=["Sistema"], summary="Informacion del servicio")
    def raiz() -> dict:
        return {
            "sistema": config.nombre,
            "empresa": config.empresa,
            "version": config.version,
            "documentacion": "/docs",
            "salud": "/salud",
        }

    @aplicacion.get("/salud", tags=["Sistema"], summary="Estado de las bases de datos")
    def salud() -> dict:
        estados: dict[str, str] = {}
        for nombre, es_rag in (("ferreteria_rag", True), ("ferreteria_usuarios", False)):
            try:
                consultar_uno("SELECT 1 AS ok", rag=es_rag)
                estados[nombre] = "operativa"
            except Exception as exc:  # noqa: BLE001 - el chequeo nunca debe fallar
                logger.warning("Chequeo de salud fallido en %s: %s", nombre, exc)
                estados[nombre] = "no disponible"

        todo_bien = all(estado == "operativa" for estado in estados.values())
        return {
            "estado": "ok" if todo_bien else "degradado",
            "bases": estados,
            "version": config.version,
        }

    return aplicacion


app = crear_aplicacion()
