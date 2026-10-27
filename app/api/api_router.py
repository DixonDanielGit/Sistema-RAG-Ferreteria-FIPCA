"""Agrupador de rutas de la version 1 de la API."""

from fastapi import APIRouter

from app.api.v1 import auth, rag_chat

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(rag_chat.router)

# Se incorporan a medida que se implementan en las semanas siguientes:
#   inventario  -> Semana 3-4 (CRUD y busqueda)
#   bitacora    -> Semana 6 (visor de auditoria)
